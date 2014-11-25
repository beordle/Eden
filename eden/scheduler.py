import logging
import time
import threading
import sys
import Queue
from eden.db import DBError
from eden.data import Backend
try:
    from thread import get_ident
except ImportError:
    from _thread import get_ident

LOGGER = logging.getLogger(__name__)

_SHUTDOWNTASK = object()



class Scheduler(object):

    # the total for worker thread to cleanly exit
    SHOTDOWN_TIMEOUT = 5

    def __init__(self, app, task_size=10, minthreads=10, maxthreads=50):
        minthreads = minthreads or 1
        minthreads = 1 if minthreads <=0 else minthreads
        maxthreads = maxthreads or 500
        maxthreads = 500 if maxthreads > 500 else maxthreads
        if maxthreads <= minthreads:
            raise TypeError('maxthreads:%d must be greater than minthreads:%d', maxthreads, minthreads)

        self.app = app
        self.ready = False 
        self.task_size = task_size or ((maxthreads - minthreads) / 2)
        self._idel_tasks = Queue.Queue()
        self.threadpool = ThreadPool(self, minthreads, maxthreads)
        self.heartbeat = HeartBeat(self._periodic_action, 5)

    def _periodic_action(self):
        idel_queue_size = self._idel_tasks.qsize()
        LOGGER.info('Idle task size: %d', idel_queue_size)
        for _ in range(idel_queue_size):
            task = self.get()
            self.execute(task, True)

    get = lambda self: self._idel_tasks.get()

    put = lambda self, task: self._idel_tasks.put(task)

    def run(self):
        LOGGER.debug('Starting schedule ....')
        LOGGER.debug('Master thread : %d', get_ident())
        self.ready = True
        self.threadpool.start()
        self.heartbeat.start()
        
        while self.ready:
            try:
                tasks = self.claim()
                if not tasks:
                    LOGGER.debug('No task sleep 5 secs')
                    time.sleep(5)
                    continue

                for task in tasks:
                    LOGGER.debug('current_task: %s', task)
                    self.execute(task)
           
            except Exception as e:
                cls, e, tb = sys.exc_info()
                LOGGER.exception('Unhandled Error %s', e)


        LOGGER.debug('Stoping schedule...')
        self.stop()

    def stop(self):
        self.heartbeat.stop()
        idel_queue_size = self._idel_tasks.qsize()
        for _ in range(idel_queue_size):
            task = self.get()
            task.retry()
            Backend('task').save(task)

        self.threadpool.stop(self.SHOTDOWN_TIMEOUT)

    def execute(self, task, retry=False):
        try:
            done = False
            thread = self.threadpool.pop()
            if thread:
                LOGGER.debug('Execute in thread: %s', thread)
                thread.current_task = task
                thread.resume()
                done = True
            elif not retry:
                LOGGER.info('Thread Pool is Full, put the the task:%s to idel_queue', task.name)
                self.put(task)
                time.sleep(1)
            else:
                task.retry()
                LOGGER.info("save task:%s to db, retry...", task.name)
                Backend('task').save(task)

        except (KeyboardInterrupt, SystemExit):
                self.ready = False
                if not done and thread:
                    thread.current_task = _SHUTDOWNTASK
                    thread.resume()
        except Exception as e:
            LOGGER.error('Execute error : %s', e)
            task.retry()
            Backend('task').save(task)

    def claim(self):
        return Backend('task').claim(self.task_size)

    @classmethod
    def add_task(cls, name, event, action, *args, **kw):
        data = {'args': args, 'kw': kw}
        task = Task(None, None, name, event, action, data)
        return Backend('task').save(job)

    @classmethod
    def stop_task(cls, name):
        task = Backend('task').find(name)
        if job and job.status != Task.RUNNING:
            task.status = Task.STOP
            Backend('task').save(task)
            return True
        return False

    @classmethod
    def delete_task(cls, name):
        task = Backend('task').find(name)
        if job and job.status != Task.RUNNING:
            Backend('task').delete(task)
            return True
        return False

class HeartBeat(threading.Thread):

    def __init__(self, callback, interval=5):
        self.callback = callback
        self.interval = interval
        self.ready = False
        threading.Thread.__init__(self)

    def run(self):
        self.ready = True
        while self.ready:
            time.sleep(self.interval)
            self.callback()

    def stop(self):
        self.ready = False
        if self.isAlive():
            self.join()
            
class ThreadPool(object):

    def __init__(self, schedule, min, max):
        self.schedule = schedule
        self.min = min
        self.max = max
        self._created = 0
        self._lock = threading.Lock()
        self._in_use_threads = {}
        self._idle_threads = []

    def start(self):
        for i in range(self.min):
            with self._lock:
                self._created += 1
                thread = self._new_thread()
                self._idle_threads.append(thread)

    def push(self, thread):
        with self._lock:
            if thread in self._in_use_threads:
                del self._in_use_threads[thread]
            self._idle_threads.append(thread)

    def pop(self):
        """Non-block pop an idle thread, if not get returns None"""
        thread = None
        self._lock.acquire()
        if self._idle_threads:
            thread = self._idle_threads.pop(0)
            self._in_use_threads[thread] = True
        elif self._created < self.max:
            self._created += 1
            thread = self._new_thread()
            self._in_use_threads[thread] = True
        self._lock.release()
        return thread

    def _new_thread(self):
        return WorkerThread(self.schedule, self)

    def stop(self, timeout=5):
        # Must shut down threads here so the code that calls
        # this method can know when all threads are stopped.

        #time.sleep(1)
        endtime = int(time.time() + timeout)
        while True:
            time.sleep(1)
            with self._lock:
                if self._in_use_threads or self._idle_threads:
                    LOGGER.info('_idle_threads')
                    while self._idle_threads:
                        worker = self._idle_threads.pop(0)
                        worker.current_task = _SHUTDOWNTASK
                        worker.resume()
                        #worker.event.clear()
                else: 
                    break


class WorkerThread(threading.Thread):

    def __init__(self, scheduler, pool):
        self.ready = False
        self.event = threading.Event()
        self.scheduler = scheduler
        self.current_task = None
        self.pool = pool
        threading.Thread.__init__(self)
        self.start()

    def suspend(self):
        self.event.clear()
        self.event.wait()

    def resume(self):
        self.event.set()

    def run(self):
        self.ready = True
        LOGGER.debug('Starting thread %d', get_ident())
        while self.ready:
            self.suspend()
            if self.current_task == _SHUTDOWNTASK:
                # shutdown the worker thread
                self.ready = False
                break
            try:
                if self.current_task:
                    self.scheduler.app(self.current_task)
                    self.current_task.fresh()
                    Backend('task').save(self.current_task)
            except Exception as e:
                cls, e, tb = sys.exc_info()
                LOGGER.exception('Unhandled Error in thread:%s %s', get_ident(),e)
                if not isinstance(e, DBError):
                    task.retry()
                    Backend('task').save(task)
            finally:
                self.current_task = None
                self.pool.push(self)
        self.event.clear()





if __name__ == '__main__':
    from eden import db
    from eden.model import Task
    from random import choice
    def app(task):
        idle = choice([0.1, 0.2, 0.5, 1, 2, 5])
        time.sleep(idle)

        LOGGER.info('Task name is : %s and %f', task.name, idle)

    # def setdebug(debug=False):
    #     level = logging.DEBUG if debug else logging.INFO
    #     logging.basicConfig(level=level,
    #                         format='%(asctime)s %(levelname)-8s %(message)s',
    #                         datefmt='%Y-%m-%d %H:%M:%S', filemode='a+')
    # setdebug(False)
    # db.setup('localhost', 'test', 'test', 'eden',
    #              pool_opt={'minconn': 3, 'maxconn': 10})

    # task = Task(None, None, 'job_test', 'job.test', {'args': (), 'kw': {}}, 'every 2')
    # db.execute('delete from cron')
    # for i in range(500):
    #     task.name = 'name_%d' %(i)
    #     Backend('task').save(task)

    # task.name = 'name_%d' %(500)
    # task.event = 'at 201411251606'
    # Backend('task').save(task)

    # scheduler = Scheduler(get_date, 20, 20, 100)
    # scheduler.run()
    import urllib2
    def get_date(task):
        date = None
        try:
            r = urllib2.urlopen('http://www.baidu.com')
            date = r.info().dict['date']
        except:
            LOGGER.info('open failed')
        LOGGER.info('Task name is : %s and date:%s', task.name, date)
    task = Task(None, None, 'job_test', 'job.test', {'args': (), 'kw': {}}, 'every 2')
    total = 0
    for i in range(100):
        s =  time.time()
        get_date(task)
        total += time.time() - s 
    print total/100




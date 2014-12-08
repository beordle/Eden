Eden
########


Eden is distributed Task system

Supports
===========

#. multi-threaded task execution (Leader/Follower variant)
#. scheduled event at a certain time or periodic execution like a crontab
#. attempting tasks that fail
#. A  threadasfe DB Api, and supports master/slave mode 
#. A Web Management Tool

.. image:: https://github.com/thomashuang/Eden/blob/master/docs/img/task.png



What will be in future
=======================

#. Add mongodb supports 
#. Improve web tool 


How to install
==============

Firstly download or fetch it form github then run the command in shell:

.. code-block:: bash

    cd Eden # the path to the project
    python setup.py install

.. note:: Make sure you had installed ``MySQLdb`` (``MySQL-python``), ``cherrypy``, ``mako`` before install the module

Compatibility
=============

Built and tested under Python 2.7 


Development
===========

Fork or download it, then run:

.. code-block:: bash 

    cd Eden # the path to the project
    python setup.py develop


Setup Database
==============

* create database in mysql:
* then run the mysql schema.sql script in the project directoy schema:

.. code-block:: bash

    mysql -u yourusername -p yourpassword yourdatabase < schema.sql


if your database has not been created yet, log into your mysql first using:

.. code-block:: bash

    mysql -u yourusername -p yourpassword yourdatabase
    mysql>CREATE DATABASE a_new_database_name
    # = you can =
    mysql> USE a_new_database_name
    mysql> source schema.sql


How to use
==========

Set and Run Web Manager
-------------------------

.. code-block:: python 

    import logging
    from eden.server import EdenWebServer
    import os.path

    from eden import db

    # setup db setting 
    # pool_opt sets the db pool min connections and max connections
    db.setup('localhost', 'test', 'test', 'eden', pool_opt={'minconn': 3, 'maxconn': 10})


    def run(host='localhost', port=80, use_gevent=False, debug=False):
        setdebug(debug)
        EdenWebServer(host=host,
                    port=port, use_gevent=use_gevent, 
                    mako_cache_dir=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache'),
                    debug=debug).serve_forever()


    def setdebug(debug=False):

        level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(level=level,
                            format='%(asctime)s %(levelname)-8s %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S', filemode='a+')

    if __name__ == '__main__':
        run(debug=True)


when firstly run the web tool, please use the root account:

:username: eden 
:password: eden

then login the web tool and change your root password.

.. note:: 


    if you wanna use gevent, please install ``gevent`` firstly, then set ``use_gevent`` to ``True``

Set up scheduler
-------------------


Here Is A Demo :

.. code-block:: python

    from eden import db
    from datetime import datetime
    import urllib2
    from eden.app import App
    from eden.scheduler import Scheduler

     if __name__ == '__main__':
        def get_date(url, session='xxx'):
            date = None
            try:
                r = urllib2.urlopen(url)
                date = r.info().dict['date']
            except:
                LOGGER.info('open failed')
            LOGGER.info('session: %s, date:%s,', session, date)
     
        def setdebug(debug=False):
            level = logging.DEBUG if debug else logging.INFO
            logging.basicConfig(level=level,
                                format='%(asctime)s %(levelname)-8s %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S', filemode='a+')
        setdebug(False)
        db.setup('localhost', 'test', 'test', 'eden',
                     pool_opt={'minconn': 3, 'maxconn': 10})
     
        app = App()
        app.add_task('task.test', get_date)
        scheduler = Scheduler(app, 20, 20, 100)
     
        db.execute('delete from cron')
        for i in range(100):
            if i % 2 == 0:
                print i
                action = 'task.not_found'
            else:
                action = 'task.test'
            scheduler.add_task('name_%d' %(i), 'every 2', action, datetime.now(), 'https://www.google.com', session=i)
        scheduler.run()

LICENSE
=======

    Copyright (C) 2014 Thomas Huang

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, version 2 of the License.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.



import logging
import threading
import time 
import json
import gzip
import logging
import time

from typing import Callable, Iterable, Optional, Any, Mapping
from autobahn.asyncio.component import Component, run
from urllib3 import request
from queue import Queue


import urllib3

MAX_REDO = 5
WAIT_FOR_REDO = 0.2 # time seconds
class PublishItem:
    def __init__(self, url=None, topic=None, data=None) -> None:
        self.url = url        
        self.data = data
        self.topic = topic

def publish_to_server(q:Queue):
    """
        this method takes is the running loop of the publishing thread.
        Params:
            q:Queue

        
        Usage:
        q = Queue()
        publisher  = Thread(target=publish_to_server, args=(q,), daemon=True)
        publisher.start()

    """
    http = urllib3.PoolManager()
    while True:
        to_publish =  q.get()

        data = {'topic': to_publish.topic, 'args': to_publish.data}
        json_data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        #compressed_data = gzip.compress(json_data)
        #print(f'rawLen: {len(json_data)} compressed: {len(compressed_data)}')

        # sometimes we recieve a ConnectionError: RemoteDisconnected('Remote end closed connection without response')
        # could not figure out who caused it and why (first detected when crossbar was running on remote server via ssl)
        # for now: try to resend the data with a few attempts. if still not possible, log and ignore.
        # TODO: have to find out if data was really not sent in such cases
        # MP 2021-04-04
        redo_count = 0
        success = False
        while success == False and redo_count < MAX_REDO:
            try:
                resp = http.request('POST', f"{to_publish.url}/publishIR",     
                    headers={'Content-Type': 'application/json', },
                    body=json_data,
                    # stream=False
                    # body=compressed_data
                )  
                # body = resp.data
                if resp.status != 200:
                    print(f'status: {resp.status} reason: {resp.reason}')
                success = True
            except urllib3.exceptions.ConnectionError:
                success = False
                redo_count += 1
                logging.getLogger("publisher").warning(f"recieved ConnectionError. retry #{redo_count}")
                time.sleep(WAIT_FOR_REDO)
        if success == False:
            
            logging.getLogger("publisher").warning(f"could not send data\ndata:{json_data}")
            # raise Exception("Could not send data")
        if redo_count > 0:
            logging.getLogger("publisher").info(f"sent data after {redo_count} attempts")


class MyPublisherAB(threading.Thread):
    """
    Not yet working as intendend. Have to handle the asyncio-event loop here since run([comp]) cannot be used.
    see https://forum.crossbar.io/t/how-can-i-open-a-connection-to-crossbar-and-publish-without-using-run-loop/1782/6

    """
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, daemon=None) -> None:
        super().__init__(group=group, target=target, name=name, args=args, kwargs=kwargs, daemon=daemon)
        self.args = args        
        self.kwargs = kwargs

        def joined(session, details):
            print("session ready")
            self.mySession = session

        comp = Component(transports="ws://host.docker.internal:8090/ws", realm=u"racelog.state")
        comp.on_join(joined)
        
        comp.start(loop=self)
        

    def run(self) -> None:
        q = self.args[0]
        count = 1
        while True:
            data = q.get()
            print(f'{count}: {len(data)}')
            count +=1
            # print(f'{self.mySession}')
            #q.task_done()


import threading
import time 
import json
import gzip
from typing import Callable, Iterable, Optional, Any, Mapping
from autobahn.asyncio.component import Component, run
from urllib3 import request
from queue import Queue

import urllib3


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
        compressed_data = gzip.compress(json_data)
        #print(f'rawLen: {len(json_data)} compressed: {len(compressed_data)}')
        resp = http.request('POST', f"{to_publish.url}/publish",     
            headers={'Content-Type': 'application/json', },
            body=json_data,
            # body=compressed_data
        )  
        if resp.status != 200:
            print(f'status: {resp.status} reason: {resp.reason}')

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

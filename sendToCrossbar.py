import json
import hashlib
from os import system

from model.cars import CarProcessor, CarsManifest
from model.pits import PitInfoManifest, PitProcessor
from model.driver import DriverProcessor
from model.msgproc import MessageProcessor, MessagesManifest
from model.session import SessionData, SessionManifest
from model.publisher import PublishItem, publish_to_server
from requests.sessions import Session
from model import Message, MessageType, StateMessage 
from queue import Queue
from threading import Thread

from enum import Enum
import sys
import irsdk
import time
import asyncio
import argparse
import yaml
import requests
import logging
import logging.config


from autobahn.asyncio.component import Component, run

class ConfigSection():
    def __init__(self, url="http://hostname:port", rpcEndpoint="racelog.state", topic="racelog.state"):        
        self.url = url
        self.rpcEndpoint = rpcEndpoint
        self.topic = topic

    
    def merge(self, **entries):
        self.__dict__.update(entries)    


class RaceStates(Enum):
    INVALID = 0
    RACING = 1
    CHECKERED_ISSUED = 2
    CHECKERED_DONE = 3
    COOLDOWN = 4
    TERMINATE = 5

class RaceState:
    """
    this class handles race sessions only. It is designed as a state machine. 
    We are only interested in data once the green flag is issued and until all available cars have crossed the s/f with checkered flag
    """
    def __init__(self, msg_proc=None, pit_proc=None, car_proc=None, driver_proc=None, ir=None) -> None:
        self.session_unique_id = -1
        self.session_num = -1
        self.msg_proc = msg_proc
        self.pit_proc = pit_proc
        self.car_proc = car_proc
        self.driver_proc = driver_proc
        self.state = RaceStates.INVALID
        self.on_init_ir_state = ir['SessionState'] # used for "race starts" message
        self.stateSwitch = {
            RaceStates.INVALID: self.state_invalid,
            RaceStates.RACING: self.state_racing,
            RaceStates.CHECKERED_ISSUED: self.state_finishing,
            RaceStates.CHECKERED_DONE: self.state_racing,
            RaceStates.COOLDOWN: self.state_cooldown,
            RaceStates.TERMINATE: self.state_terminate,
        }

        

    def reset(self):
        pass

    def state_invalid(self,ir):
        if ir['SessionInfo']['Sessions'][ir['SessionNum']]['SessionType'] == 'Race':
            if ir['SessionState'] == irsdk.SessionState.racing:
                logger.info(f'=== Race state detected ===')
                self.pit_proc.race_starts(ir)
                self.car_proc.race_starts(ir)
                self.state = RaceStates.RACING
                if self.on_init_ir_state != ir['SessionState']:
                    logger.info(f'real race start detected')
                    self.msg_proc.add_race_starts()
                    pass

    def state_racing(self,ir):
        if ir['SessionState'] == irsdk.SessionState.checkered:
            logger.info(f'checkered flag issued')
            self.state = RaceStates.CHECKERED_ISSUED
            self.car_proc.checkered_flag(ir)
            self.msg_proc.add_checkered_issued()
            # need to check where the leader is now. has he already crossed s/f ? 
            # (problem is a about to be lapped car in front of that car - which of course should not yet be considered as a finisher)
            return 
        self.pit_proc.process(ir)
        # state.driver_proc.process(ir)
        self.car_proc.process(ir, self.msg_proc)

    def state_finishing(self,ir):
        if ir['SessionState'] == irsdk.SessionState.cool_down:
            # TODO: at this point the last car may not be processed in the standings. check when time
            # idea: separate into two state: cooldown_issued. after  5s  all missing data should be processed. After that terminate.
            self.car_proc.process(ir, self.msg_proc)
            logger.info(f'cooldown signaled - get out of here')
            self.state = RaceStates.COOLDOWN
            self.cooldown_signaled = time.time()
            return

        self.pit_proc.process(ir)        
        self.car_proc.process(ir, self.msg_proc)

    def state_cooldown(self, ir):
        """
        on cooldown notice we want to stay 5 more secs active to get the latest standings.
        """
        if (time.time() - self.cooldown_signaled) < 5:
            self.car_proc.process(ir, self.msg_proc)
            return
        else: 
            logger.info(f'internal cooldown phase done. Terminating now')
            self.state = RaceStates.TERMINATE
            return

    def state_terminate(self, ir ):
        # TODO: think about shutting down only when specific config attribute is set to do so ;)
        # for now it is ok.
        logger.info(f'unregister service')
        unregister_service()
        logger.info(f'unregister called')
        sys.exit(0)
        logger.error(f'should not see this')

    def handle_new_session(self,ir):
        self.msg_proc.clear_buffer()
        self.pit_proc.clear_buffer()
        # state.car_proc.clear_buffer()
        self.session_num = ir['SessionNum']
        self.session_unique_id = ir['SessionUniqueID']
        state.last_publish = -1
        self.state = RaceStates.INVALID
        self.on_init_ir_state = ir['SessionState'] # used for "race starts" message
        # state.last_data.speedmap = SpeedMap(state.track_length)
        logger.info(f'new unique session detected: {self.session_unique_id} sessionNum: {self.session_num}')

    def process(self, ir):        
        # handle global changes here
        if ir['SessionUniqueID'] != 0 and ir['SessionUniqueID'] != self.session_unique_id:
            self.handle_new_session(ir)
        # handle processing depending on current state
        self.stateSwitch[self.state](ir)


# this is our State class, with some helpful variables
class State:
    def __init__(self) -> None:
        self.reset()

    def reset(self):
        self.ir_connected = False
        self.last_car_setup_tick = -1
        self.lastWI = None
        self.lastDI = None
        self.lastSI = None
        # own entries start here
        self.last_session_state = -1
        self.last_session_num = -1
        self.last_session_unique_id = -1
        self.last_publish = -1
        self.msg_proc = None
        self.driver_proc = None
        self.pit_proc = None
        self.car_proc = None
        self.racelog_event_key = None
        self.racestate = None

def publish_current_state():
    # msg = Message(type=MessageType.STATE.value, payload={'session': {'sessionTime':ir['SessionTime']}})
    sessionData = SessionData(ir)
    messages = state.msg_proc.manifest_output()
    cars = state.car_proc.manifest_output()
    pits = state.pit_proc.manifest_output()
    stateMsg = StateMessage(session = sessionData.manifest_output(), messages=messages, cars=cars, pits=pits)
    
    msg = Message(type=MessageType.STATE.value, payload=stateMsg.__dict__)

    data = {'topic': f'{crossbarConfig.topic}.{state.racelog_event_key}', 'args': [msg.__dict__]}
    #json_data = json.dumps(data, ensure_ascii=False)
    to_publish = PublishItem(url=crossbarConfig.url, topic=f'{crossbarConfig.topic}.{state.racelog_event_key}', data=[msg.__dict__])
    q.put(to_publish)
    q.task_done()
    state.msg_proc.clear_buffer()
    state.pit_proc.clear_buffer()
    

def register_service():
    """
        registers this timing provider at the manager
    """
    state.racelog_event_key = hashlib.md5(ir['WeekendInfo'].__repr__().encode('utf-8')).hexdigest()
    logger.info(f"Registering with id {state.racelog_event_key}")
    register_data = {'id': state.racelog_event_key, 'manifests': {'car': state.car_proc.manifest, 'session': SessionManifest, 'pit': PitInfoManifest, 'message': MessagesManifest}}
    data = {'procedure': 'racelog.register_provider', 'args': [register_data]}
    resp = requests.post(f"{crossbarConfig.url}/call",     
            headers={'Content-Type': 'application/json'},
            json=data
        )    
    if (resp.status_code != 200):
        print(f"warning: {resp.status_code}")
    pass

def unregister_service():
    """
        registers this timing provider at the manager
    """
    
    # unregister_data = {'id': state.racelog_event_key}
    data = {'procedure': 'racelog.remove_provider', 'args': [state.racelog_event_key]}
    resp = requests.post(f"{crossbarConfig.url}/call",     
            headers={'Content-Type': 'application/json'},
            json=data
        )    
    if (resp.status_code != 200):
        print(f"warning: {resp.status_code}")
    pass

# to be deleted! RaceState takes over
def handle_new_session():
    state.msg_proc.clear_buffer()
    state.pit_proc.clear_buffer()
    # state.car_proc.clear_buffer()
    state.last_session_num = ir['SessionNum']
    state.last_session_unique_id = ir['SessionUniqueID']
    state.last_publish = -1
    state.racestate.handle_new_session(ir)
    # state.last_data.speedmap = SpeedMap(state.track_length)
    logger.info(f'new unique session detected: {state.last_session_unique_id} sessionNum: {state.last_session_num}')


# here we check if we are connected to iracing
# so we can retrieve some data
def check_iracing():
    if state.ir_connected and not (ir.is_initialized and ir.is_connected):
        state.ir_connected = False
        # don't forget to reset your State variables
        state.last_car_setup_tick = -1
        state.last_publish = -1
        # we are shutting down ir library (clearing all internal variables)
        ir.shutdown()
        print('irsdk disconnected')
        unregister_service()
        sys.exit(0)
    elif not state.ir_connected and ir.startup() and ir.is_initialized and ir.is_connected:
        state.reset()
        state.ir_connected = True
        state.driver_proc = DriverProcessor(current_ir=ir)
        state.msg_proc = MessageProcessor(state.driver_proc)
        state.pit_proc = PitProcessor(current_ir=ir, msg_proc=state.msg_proc, driver_proc=state.driver_proc)
        state.car_proc = CarProcessor(state.driver_proc, ir)
        state.last_session_state = ir['SessionState']
        state.last_session_num = ir['SessionNum']
        state.last_session_unique_id = ir['SessionUniqueID']
        state.racestate = RaceState(state.msg_proc, state.pit_proc, state.car_proc, state.driver_proc, ir)
        register_service()
        print('irsdk connected')



# our main loop, where we retrieve data
# and do something useful with it
def loop():
    # on each tick we freeze buffer with live telemetry
    # it is optional, but useful if you use vars like CarIdxXXX
    # this way you will have consistent data from those vars inside one tick
    # because sometimes while you retrieve one CarIdxXXX variable
    # another one in next line of code could change
    # to the next iracing internal tick_count
    # and you will get incosistent data
    ir.freeze_var_buffer_latest()

    # retrieve live telemetry data
    # check here for list of available variables
    # https://github.com/kutu/pyirsdk/blob/master/vars.txt
    # this is not full list, because some cars has additional
    # specific variables, like break bias, wings adjustment, etc
    t = ir['SessionTime']
    #print('session time:', t)
    if t == 0.0:
        # there are race situatione where the whole ir-Data are filled with 0 bytes. Get out of here imediately
        logger.warning("Possible invalid data in ir - session time is 0.0. skipping loop")
        return

    if ir['DriverInfo']:
        if (ir['DriverInfo'] != state.lastDI):
            #print(ir['DriverInfo'])
            state.lastDI = ir['DriverInfo'];
            state.driver_proc.process(ir,state.msg_proc, state.pit_proc)

    state.racestate.process(ir)
    
    #process_changes_to_last_run(state.last_data)
    if ((t - state.last_publish) > 1):
        # this is the point where we want to send the data to the server. 
        # By now we just log something....
        publish_current_state()
        # print('session time:', t)
        state.last_publish = t
    

VERSION = "0.1"
crossbarConfig = ConfigSection()
q = Queue()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', action='version', version='fake data provider %s' % VERSION, help='show version and exit')
    parser.add_argument('--url', help='sets the url for the backend')
    parser.add_argument('--crossbar', help='sets the url for the backend')
    parser.add_argument('--config',  help='use this config file', default="config.yaml")
        
    #args = parser.parse_known_args()
    args = parser.parse_args()

    configFilename = "config.yaml"
    if args.config:
        configFilename = args.config
    try:
        with open(configFilename, "r") as ymlfile:
            cfg = yaml.safe_load(ymlfile)
            if "crossbar" in cfg.keys():
                crossbarConfig.merge(**cfg['crossbar'])
    except IOError as e:
        print(f'WARN: Could not open {configFilename}: {e}. continuing...')

    if args.crossbar:
        crossbarConfig.url = args.crossbar

    print(f'Using this url: {crossbarConfig.url}')

    with open('logging-crossbar.yaml', 'r') as f:
        config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    # initializing ir and state
    logger = logging.getLogger("racelog")

    ir = irsdk.IRSDK()
    state = State()
    publisher = Thread(group=None, target=publish_to_server, name="MyPublisher", args=(q,))
    publisher.start()
    try:
        # infinite loop
        while True:
            # check if we are connected to iracing
            check_iracing()
            # if we are, then process data
            if state.ir_connected:
                loop()
            # sleep for 1 second
            # maximum you can use is 1/60
            # cause iracing updates data with 60 fps
            time.sleep(1/60)
    except KeyboardInterrupt:        
        # try:
        #     unregister_service()
        # except:
        #     pass
        # press ctrl+c to exit
        pass

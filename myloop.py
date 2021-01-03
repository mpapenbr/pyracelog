#!python3

from json import encoder
import irsdk
import time
import re
import json
from requests.sessions import session 
import websockets
import asyncio
import requests
import copy
import gzip
import codecs
from datetime import datetime
class PitInfo:
    car_idx = 0
    pit_lane_time = 0
    pit_stop_time= 0
    
    lane_enter_time = 0   
    pit_stop_start_time = 0
    stop_enter_time = 0

class LapInfo:
    car_idx = 0
    lapno = 0
    laptime = 0    
    sectors = []

    lap_start_time = 0 # holds the session time when the lap begins
    cur_sector = 0 # holds the current sector where the car is located
    cur_sector_start_time = 0 # holds the session time when the current began
    


class DataStore:
    def __init__(self) -> None:
        super().__init__()
        self.reset_values()

    def reset_values(self):
        """
        This holds data retrieved/computed on every step. 
        TODO: The data sent to the server is extracted from here
        """
        self.car_idx_position = []        
        self.car_idx_class_position = []
        self.car_idx_lap_dist_pct = []
        self.car_idx_lap = []
        self.car_idx_lap_completed = []
        self.car_idx_last_laptime = []
        
        self.car_idx_on_pitroad = []
        self.session_tick = 0
        self.session_time = 0
        self.session_time_remain = 0
        self.session_time_of_day = 0
        self.session_num = 0
        self.session_flags = 0
        self.session_state = 0
        self.track_temp_crew = 0
        self.track_temp = 0
        self.air_temp = 0
        self.air_pressure = 0
        self.air_density = 0


        self.car_idx_lap_sectors = [64][:]
        self.car_idx_speed = [] # car speed  (calculated)
        self.car_idx_delta = [] # delta to car in front (by position)
        self.car_idx_dist_meters = [] # distance in m to car in front (right now for debugging)
        # collector for uploads

        self.finished_pits = [] # all finished pit stop between 2 uploads are stored here
        self.finished_laps = [] # all finished laps between 2 uploads are stored here

        self.work_pit_stop = {}
        self.lap_info = {}


# this is our State class, with some helpful variables
class State:
    ir_connected = False

    last_car_setup_tick = -1
    last_data = DataStore() # this holds my required data of the previous tick
    last_publish = -1
    last_session_num = -1 # we need this to detect session change
    track_length = 0
    pace_car_idx = 0
    

    lastWI = None
    lastDI = None
    lastSI = None
    lastSectorInfo = None

    driver_info_need_transfer = False
    session_need_transfer = False

    # racelog server
    race_log_base_url = None

    def __init__(self) -> None:
        super().__init__()
        self.ir_connected = False
        self.reset_values()

    def reset_values(self):
        self.last_car_setup_tick = -1
        self.last_data = DataStore() # this holds my required data of the previous tick
        self.last_publish = -1
        self.track_length = 0
        self.pace_car_idx = 0
        self.last_session_num = -1
        

        self.lastWI = None
        self.lastDI = None
        self.lastSI = None
        self.lastSectorInfo = None

        self.driver_info_need_transfer = False
        self.session_need_transfer = False

        # racelog server
        self.race_log_base_url = None


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
        state.json_log_file.close()

    elif not state.ir_connected and ir.startup() and ir.is_initialized and ir.is_connected:
        state.ir_connected = True
        state.reset_values()
        print('irsdk connected')
        connect_racelog()
        print('racelog connected')
        timestr = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        state.json_log_file = codecs.open(f"send-data-{timestr}.json", "w", encoding='utf-8')
        # state.json_log_file = open(f"send-data-{timestr}.json", "w")

def connect_racelog():
    ir.freeze_var_buffer_latest()    
    
    if (ir['SessionUniqueId'] == 1): 
        data = {}
    else:
        data = {'sessionId': ir['SessionUniqueId']}
    
    # TODO: API-Key
    resp = requests.post("http://localhost:8082/raceevents/request",     
    #resp = requests.post("http://host.docker.internal:8080/raceevents/request",     
    headers={'Content-Type': 'application/json'},
    json=data)
    # TODO: error handling
    state.race_log_base_url = resp.headers['Location']
    

def save_step_data(data:DataStore):
    data.session_time = current_ir_session_time()
    data.session_tick = ir['SessionTick']
    data.session_time_remain = ir['SessionTimeRemain']
    data.session_time_of_day = ir['SessionTimeOfDay']
    data.session_laps_remain = ir['SessionLapsRemain']
    data.session_num = ir['SessionNum']
    data.session_flags = ir['SessionFlags']
    data.session_state = ir['SessionState']
    data.air_density = ir['AirDensity']
    data.air_pressure = ir['AirPressure']
    data.air_temp = ir['AirTemp']
    data.track_temp = ir['TrackTemp']
    data.track_temp_crew = ir['TrackTempCrew']
    data.car_idx_lap = ir['CarIdxLap'] 
    data.car_idx_lap_completed = ir['CarIdxLapCompleted'] 
    data.car_idx_position = ir['CarIdxPosition'] 
    data.car_idx_class_position = ir['CarIdxClassPosition'] 
    data.car_idx_lap_dist_pct = ir['CarIdxLapDistPct']
    data.car_idx_on_pitroad = ir['CarIdxOnPitRoad']
    data.car_idx_last_laptime = ir['CarIdxLastLapTime']

    

def handle_new_session():
    state.last_data.reset_values()
    state.last_session_num = ir['SessionNum']
    state.last_publish = -1

def log_current_info():
    # print(ir['CarIdxLapDistPct'][0:6])

    sectors = [[] for x in range(64)];
    for item in state.last_data.lap_info.values():
        # print(f'{item.car_idx}: f:{item.sectors}')
        sectors[item.car_idx] = item.sectors
        
    

    race_data = {
        'carIdxLapDistPct': state.last_data.car_idx_lap_dist_pct,
        'carIdxPosition': state.last_data.car_idx_position,
        'carIdxClassPosition': state.last_data.car_idx_class_position,
        'carIdxLap': state.last_data.car_idx_lap,
        'carIdxLapCompleted': state.last_data.car_idx_lap_completed,
        'carIdxOnPitRoad': state.last_data.car_idx_on_pitroad,
        'carIdxLastLapTime': state.last_data.car_idx_last_laptime,

        'carIdxLapSectors': sectors,
        'carIdxSpeed': state.last_data.car_idx_speed,
        'carIdxDelta': state.last_data.car_idx_delta,
        'carIdxDistMeters': state.last_data.car_idx_dist_meters,

        'sessionTime': current_ir_session_time(),
        'sessionTick': state.last_data.session_tick,
        'sessionTimeRemain': state.last_data.session_time_remain,
        'sessionTimeOfDay': state.last_data.session_time_of_day,
        'sessionNum': state.last_data.session_num,
        'sessionFlags': state.last_data.session_flags,
        'sessionState': state.last_data.session_state,
        'airDensity': state.last_data.air_density,
        'airPressure': state.last_data.air_pressure,
        'airTemp': state.last_data.air_temp,
        'trackTemp': state.last_data.track_temp,
        'trackTempCrew': state.last_data.track_temp_crew,

    }
    pit_stops = [{
        'carIdx': p.car_idx,
        'pitLaneTime': p.pit_lane_time,
        'pitStopTime': p.pit_stop_time,
        'laneEnterTime': p.lane_enter_time,
        'stopEnterTime': p.stop_enter_time
    } for p in state.last_data.finished_pits]
    
   
    own_laps = [{
        'carIdx': p.car_idx,
        'lapNo': p.lapno,
        'lapTime': p.laptime,
        'sectors': p.sectors
    } for p in state.last_data.finished_laps]

    driver_info = []
    if (state.driver_info_need_transfer):
        driver_info = [{
            'carIdx': di['CarIdx'],
            'carId': di['CarID'],
            'carClassId': di['CarClassID'],
            'carClassShortName': di['CarClassShortName'],
            'carNumber': di['CarNumber'],
            'carNumberRaw': di['CarNumberRaw'],
            'carName': di['CarScreenName'],
            'carShortName': di['CarScreenNameShort'],
            'iRating': di['IRating'],
            'teamId': di['TeamID'],
            'userId': di['UserID'],
            'userName': di['UserName'],
            'teamName': di['TeamName'],
            
        } for di in state.lastDI['Drivers'] if not (di['CarIsPaceCar']==1 or di['IsSpectator']==1)]
        state.driver_info_need_transfer = False
    result_info = []
    if (state.session_need_transfer):
        if state.lastSI['Sessions'][ir['SessionNum']]['ResultsPositions'] != None:
            result_info = [{
                'carIdx': rp['CarIdx'],
                'classPosition': rp['ClassPosition'],
                'lap': rp['Lap'],
                'lapsComplete': rp['LapsComplete'],
                'lapsDriven': rp['LapsDriven'],
                'position': rp['Position'],
                'reasonOut': rp['ReasonOutStr'],
                'delta': rp['Time'],

            } for rp in state.lastSI['Sessions'][ir['SessionNum']]['ResultsPositions']]
            state.session_need_transfer = False

    data = {'raceData': race_data, 'pitStops': pit_stops, 'driverData': driver_info, 'resultData': result_info, 'ownLaps': own_laps}
    json_data = json.dumps(data, ensure_ascii=False)
    state.json_log_file.write(f'{json_data}\n')
    # decompression is not yet implemented on server side
    # post_data = gzip.compress(json.dumps(data).encode('utf-8'))
    resp = requests.post(f"{state.race_log_base_url}/racedata",     
    headers={'Content-Type': 'application/json'},
    json=data)
    if (resp.status_code != 200):
        print(f"warning: {resp.status_code}")
    else:
        state.last_data.finished_pits = []
        state.last_data.finished_laps = []
    
def handle_weekend_info():
    sessions = [{
        'num': s['SessionNum'],
        'name': s['SessionName'],
        'type': s['SessionType']
        } for s in ir['SessionInfo']['Sessions']]
    data = {
        'trackId': state.lastWI['TrackID'],
        'trackNameShort': state.lastWI['TrackDisplayShortName'],
        'trackNameLong': state.lastWI['TrackDisplayName'],
        'trackConfig': state.lastWI['TrackConfigName'],
        'trackLength': state.track_length,
        'teamRacing': state.lastWI['TeamRacing'],
        'numCarClasses': state.lastWI['NumCarClasses'],
        'numCarTypes': state.lastWI['NumCarTypes'],
        'eventStart': datetime.strptime(f"{state.lastWI['WeekendOptions']['Date']} {state.lastWI['WeekendOptions']['TimeOfDay']}", '%Y-%m-%d %I:%M %p').isoformat(),
        'sessions': sessions

    }
    resp = requests.put(f"{state.race_log_base_url}",     
    headers={'Content-Type': 'application/json'},
    json=data)
    if (resp.status_code != 200):
        print(f"warning: {resp.status_code}")

def delta_distance(a,b):
    if a > b:
        return a-b
    else:
        return 1-b+a

def handle_pitstops(data:DataStore):
    """
    Pit stops are measured like this:
    - CarIdxOnPitRoad changed 
    - from false to true: start pit lane timer
    - from true to false: end pit lane time
    - if true and "car did not move": start pit stop timer
    - if true and "car moved": end pit stop timer
      
    """
    
    pit = ir['CarIdxOnPitRoad']
    if (len(pit) != len(data.car_idx_on_pitroad)):
        return
    # this is useful for debugging sessions
    if (current_ir_session_time() == data.session_time):
        return
    for i in range(0, len(pit)):
        if (pit[i] and not data.car_idx_on_pitroad[i]):
            #print(f"Car {i} entered pit")
            work = PitInfo()
            work.car_idx = i
            work.lane_enter_time = current_ir_session_time()
            data.work_pit_stop[i] = work

        if (pit[i] and data.car_idx_on_pitroad[i] and i in data.work_pit_stop.keys()):
            pit_info = data.work_pit_stop[i]
            track_length = state.track_length
            move_dist_pct = delta_distance(ir['CarIdxLapDistPct'][i],data.car_idx_lap_dist_pct[i])            
            speed = move_dist_pct*track_length/(current_ir_session_time() - data.session_time) * 3.6
            # print(f"moveDist: {moveDistPct} speed: {speed}")
            if (pit_info.pit_stop_start_time == 0 and  speed < 1):
                #print(f"Car {i} stopped at pit")
                pit_info.pit_stop_start_time = current_ir_session_time()
                pit_info.stop_enter_time = current_ir_session_time()
            
            if (pit_info.pit_stop_start_time != 0 and speed > 5):
                #print(f"Car {i} about to leave pit")            
                pit_info.pit_stop_time= current_ir_session_time() - pit_info.pit_stop_start_time
                #print(f"Car {i} pit stop duration: {pit_info.pit_stop_time}")
                pit_info.pit_stop_start_time = 0 # reset the pit stop timer



        if (not pit[i] and data.car_idx_on_pitroad[i] and i in data.work_pit_stop.keys()):
            pit_info = data.work_pit_stop[i]
            pit_info.pit_lane_time = current_ir_session_time() - pit_info.lane_enter_time 
            #print(f"Car {i} left pit lane: duration: {pit_info.pit_lane_time}")
            data.finished_pits.append(copy.deepcopy(pit_info))
            #print(f"now in finished_pits: {data.finished_pits}")

def get_current_sector(lapDitPct:float) -> int:
    i = len(state.lastSectorInfo)-1    
    try:
        while lapDitPct < state.lastSectorInfo[i]['SectorStartPct']:
            i = i - 1
        return i
        
    except Exception as identifier:
        print(f'{lapDitPct} {i}')
        raise
        


def handle_cross_the_line(data:DataStore):
    current = ir['CarIdxLapDistPct']
    if (len(data.car_idx_lap_dist_pct) != len(current)):
        return
    for i in range(0, len(current)):
        adjustedDistPct = current[i]
        if (current[i]> -1 and current[i] < 0):
            # there are some cases when crossing s/f where distPct is a small value negative value. 
            # this gets adjusted to 0
            print(f'{current_ir_session_time()} WARNING: Car {i} has invalid distPct of {current[i]}')
            adjustedDistPct = 0
            

        if (adjustedDistPct < 0):            
            continue

        if i == state.pace_car_idx:
            continue
        
        if i in data.lap_info.keys():
            sector = get_current_sector(adjustedDistPct)
            work = data.lap_info[i]
            if (sector != work.cur_sector):
                # sector change detected. compute the duration of the last sector
                sector_time = current_ir_session_time() - work.cur_sector_start_time
                work.sectors.append(sector_time)
                # print(f'New sector time car {i} sector {work.cur_sector}: {sector_time}')
                work.cur_sector = sector
                work.cur_sector_start_time = current_ir_session_time()

        currentLap = ir['CarIdxLap'] 
        if (currentLap[i] != data.car_idx_lap[i]):
            if i in data.lap_info.keys():
                # we have data from the previous beginning, lets calc now
                work = data.lap_info[i]
                work.laptime = current_ir_session_time() - work.lap_start_time
                # print(f'Car {i}: laptime {work.laptime} sectors: {work.sectors}')
                data.finished_laps.append(copy.deepcopy(work))
            
            work = LapInfo()
            work.car_idx = i
            work.lapno = currentLap[i]
            work.lap_start_time = current_ir_session_time()
            work.cur_sector_start_time = work.lap_start_time
            work.cur_sector = 0
            work.sectors = []
            data.lap_info[i] = work




def handle_time_update(data:DataStore):
    handle_cross_the_line(data)

def handle_speeds(data:DataStore):
    current_pct = ir['CarIdxLapDistPct']
    current_lap = ir['CarIdxLap']
    if len(data.car_idx_lap_dist_pct) != len(current_pct):
        return
        
    data.car_idx_speed = [0 for i in range(len(current_pct))]
    data.car_idx_delta = [0 for i in range(len(current_pct))]
    data.car_idx_dist_meters = [0 for i in range(len(current_pct))]
    for i in range(len(current_pct)):
        if (current_pct[i] > -1):            
            move_dist_pct = delta_distance(current_pct[i],data.car_idx_lap_dist_pct[i])
            delta_time = current_ir_session_time() - data.session_time
            if delta_time != 0:
                data.car_idx_speed[i] = move_dist_pct*state.track_length/delta_time * 3.6
            else:
                data.car_idx_speed[i] = 0
    
    current_race_order = [(i, current_lap[i]+current_pct[i])  for i in range(0,len(current_lap))]
    current_race_order.sort(key = lambda k: k[1], reverse=True)
   

    for i in range(1, len(current_race_order)):          
        item = current_race_order[i]      
        if (item[1] < 0):
            continue
        data.car_idx_dist_meters[item[0]] =  delta_distance(current_pct[current_race_order[i-1][0]], current_pct[item[0]]) * state.track_length            
        if data.car_idx_speed[item[0]] == 0:
            data.car_idx_delta[item[0]] = 999
        else:
            data.car_idx_delta[item[0]] = data.car_idx_dist_meters[item[0]] / (data.car_idx_speed[item[0]] / 3.6)


def current_ir_session_time():
    return ir['SessionTime'];


def process_changes_to_last_run(data:DataStore):
    handle_pitstops(data)    
    handle_time_update(data)
    handle_speeds(data)

def get_track_length_in_meters(arg:str) -> float:
    milesInKm = 1.60934
    m = re.search(r'(?P<length>(\d+\.\d+)) (?P<unit>(km|mi))', arg) 
    if (m.group('unit') == 'mi'):
        return float(m.group('length')) * milesInKm * 1000;
    else:
        return float(m.group('length')) * 1000



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

    if ir['SessionNum'] != state.last_session_num:
        handle_new_session()

    if ir['WeekendInfo']:
        if (ir['WeekendInfo'] != state.lastWI):
            #print(ir['WeekendInfo'])
            state.lastWI = ir['WeekendInfo'];
            state.track_length = get_track_length_in_meters(state.lastWI['TrackLength'])
            print(f"Track length is {state.track_length:5.0f} m")
            handle_weekend_info()
        #print(ir['WeekendInfo']['TeamRacing'])


    if ir['SplitTimeInfo']:
        if (ir['SplitTimeInfo']['Sectors'] != state.lastSectorInfo):
            #print(ir['SplitTimeInfo'])
            state.lastSectorInfo = ir['SplitTimeInfo']['Sectors'];

    if ir['DriverInfo']:
        if (ir['DriverInfo'] != state.lastDI):
            #print(ir['DriverInfo'])
            state.lastDI = ir['DriverInfo'];
            # paceCarEntry = [value for value in state.lastDI['Drivers'] if value['CarIsPaceCar'] == 1]
            state.pace_car_idx = ir['DriverInfo']['PaceCarIdx']
            print(f'PaceCar-Idx: {state.pace_car_idx}')
            state.driver_info_need_transfer = True

    if ir['SessionInfo']:
        if (ir['SessionInfo'] != state.lastSI):
            print('got new SessionInfo record')
            # print(ir['SessionInfo'])
            state.lastSI = ir['SessionInfo'];
            state.session_need_transfer = True
    # retrieve live telemetry data
    # check here for list of available variables
    # https://github.com/kutu/pyirsdk/blob/master/vars.txt
    # this is not full list, because some cars has additional
    # specific variables, like break bias, wings adjustment, etc

    t = ir['SessionTime']
    process_changes_to_last_run(state.last_data)
    if ((t - state.last_publish) > 1):
        # this is the point where we want to send the data to the server. 
        # By now we just log something....
        log_current_info()
        # print('session time:', t)
        state.last_publish = t

    save_step_data(state.last_data)

    # and just as an example
    # you can send commands to iracing
    # like switch cameras, rewind in replay mode, send chat and pit commands, etc
    # check pyirsdk.py library to see what commands are available
    # https://github.com/kutu/pyirsdk/blob/master/irsdk.py#L134 (class BroadcastMsg)
    # when you run this script, camera will be switched to P1
    # and very first camera in list of cameras in iracing
    # while script is running, change camera by yourself in iracing
    # and notice how this code changes it back every 1 sec
    # ir.cam_switch_pos(0, 1)

if __name__ == '__main__':
    # initializing ir and state
    ir = irsdk.IRSDK()
    state = State()

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
        # press ctrl+c to exit
        pass

import sys
import re
import logging

CarsManifest = ['state','carIdx','carNum','userName','teamName','carClass','pos','pic','lap','lc','gap','interval','trackPos','speed','dist','pit','last','best']


def gate(v):
    if v < 0:
        return 0
    if v > 1:
        return 1
    return v

def delta_distance(a,b):
    if a >= b:
        return a-b
    else:
        return a+1-b

def delta_to_prev(a,b):
    d = abs(a-b)    
    if d > 0.5:
        return 1-d
    else:
        return d


class CarData:
    def __init__(self,manifest=CarsManifest) -> None:
        self.current_best = sys.maxsize
        self.manifest = manifest
        for item in manifest:
            self.__setattr__(item, "")
    
    def __setitem__(self,key,value):
        self.__setattr__(key,value)
    
    def __getitem__(self,key):
        self.__getattribute__(key)
    
    def manifest_output(self):
        return [self.__getattribute__(x) for x in self.manifest]

class CarProcessor():
    def __init__(self,driver_proc=None, current_ir=None, manifest=CarsManifest) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.driver_proc = driver_proc
        self.lookup = {}
        self.manifest = manifest
        self.prev_dist_pct = []
        self.prev_time = current_ir['SessionTime']

        milesInKm = 1.60934
        m = re.search(r'(?P<length>(\d+\.\d+)) (?P<unit>(km|mi))', current_ir['WeekendInfo']['TrackLength']) 
        if (m.group('unit') == 'mi'):
            self.track_length = float(m.group('length')) * milesInKm * 1000;
        else:
            self.track_length =  float(m.group('length')) * 1000
        print(f"TrackLength: {self.track_length}")
        self.min_move_dist_pct = 0.1/self.track_length # if a car doesn't move 10cm in 1/60s 


    def process(self,ir):
        for idx in range(64):     
            if idx == ir['DriverInfo']['PaceCarIdx']:
                continue
            if  ir['CarIdxLapDistPct'][idx] > -1:                
                if idx not in self.lookup.keys():
                    work = CarData(self.manifest)
                    self.lookup[idx] = work
                else:
                    work = self.lookup.get(idx)
                work['state'] = 'RUN'
                if ir['CarIdxOnPitRoad'][idx]:
                    work['state'] = 'PIT'
                work['carIdx'] = idx
                work['carNum'] = self.driver_proc.car_number(idx)
                work['userName'] = self.driver_proc.user_name(idx)
                work['teamName'] = self.driver_proc.team_name(idx)
                work['carClass'] = self.driver_proc.car_class(idx)
                work['pos'] = ir['CarIdxPosition'][idx]
                work['pic'] = ir['CarIdxClassPosition'][idx]
                work['lap'] = ir['CarIdxLap'][idx]
                work['lc'] = ir['CarIdxLapCompleted'][idx]
                #TODO work['gap'] = ""
                #TODO work['interval'] = ""
                work['trackPos'] = gate(ir['CarIdxLapDistPct'][idx])
                work['last'] = ir['CarIdxLastLapTime'][idx]
                work['best'] = ir['CarIdxBestLapTime'][idx]      
            
                work['speed'] = self.calc_speed(ir, idx)
            else:
                # handle those cars which have an entry in driver but do not appear valid in CarIdxLapDistPct
                # these cars may be out of the race...
                pass
        self.prev_dist_pct = ir['CarIdxLapDistPct'][:] # create a copy for next run
        self.prev_time = ir['SessionTime']


    def calc_speed(self, ir, idx):
        current_dist = ir['CarIdxLapDistPct'][idx]
        t = ir['SessionTime']
        if len(self.prev_dist_pct) != len(ir['CarIdxLapDistPct']):
            return -1
        move_dist_pct = delta_to_prev(gate(current_dist), gate(self.prev_dist_pct[idx]))
        delta_time = ir['SessionTime'] - self.prev_time
        if (delta_time != 0):
            if move_dist_pct < self.min_move_dist_pct or move_dist_pct > (1-self.min_move_dist_pct):                    
                if ir['CarIdxOnPitRoad'][idx] == False:
                    self.logger.debug(f'STime: {ir["SessionTime"]:.0f} carIdx: {idx} curPctRaw: {current_dist} prevPctRaw: {self.prev_dist_pct[idx]} dist: {move_dist_pct} did not move min distance')
                return 0

            speed = move_dist_pct*self.track_length/delta_time * 3.6
            
            if (speed > 400):
                self.logger.warning(f'STime: {ir["SessionTime"]:.0f} Speed > 400: {speed} carIdx: {idx} curPctRaw: {current_dist} prevPctRaw: {self.prev_dist_pct[idx]} dist: {move_dist_pct} dist(m): {move_dist_pct*self.track_length} deltaTime: {delta_time}')
                return -1
            # TODO: Speedmap !!
            return speed
        else:
            return 0

    def manifest_output(self):
        
        current_race_order = [(i.carIdx, i.lap+i.trackPos)  for i in self.lookup.values()]
        current_race_order.sort(key = lambda k: k[1], reverse=True)
        ordered = [self.lookup[item[0]] for item in current_race_order]
        return [[getattr(m, x) for x in self.manifest] for m in ordered]
        
        
        
import sys
import re
import logging
import math
from speedmap import SpeedMap

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

def laptimeStr(t):
    work = t;
    minutes = t // 60;
    work -= minutes * 60;
    seconds = math.trunc(work);
    work -= seconds;
    hundrets = math.trunc(work * 100);
    if minutes > 0 :
        return f"{minutes:.0f}:{seconds:02d}.{hundrets:02d}"
    else:
        return f"{seconds:02d}.{hundrets:02d}"
        



class SectionTiming:
    """
    this class is used to measure a sector time or a complete lap time.
    The key attr identifies a sector or lap number
    """
    def __init__(self) -> None:
        self.start_time = -1
        self.stop_time = -1
        self.duration = -1
        self.best = sys.maxsize
        
    
    def mark_start(self,sessionTime):
        self.start_time = sessionTime
        
    def mark_stop(self,sessionTime):
        self.stop_time = sessionTime
        self.duration = self.stop_time - self.start_time
        return self.duration
        # self.best = min(self.best,self.duration)



class CarLaptiming:
    def __init__(self, num_sectors=0) -> None:
        self.lap = SectionTiming()
        self.sectors = [SectionTiming() for x in range(num_sectors)]

    def reset(self):
        pass
class CarData:
    """
    this class holds data about a car during a race. 
    No data history is stored here.
    """
    def __init__(self,manifest=CarsManifest,num_sectors=0) -> None:
        self.current_best = sys.maxsize
        self.manifest = manifest
        self.slow_marker = False
        self.current_sector = -1
        self.lap_timings = CarLaptiming(num_sectors=num_sectors)

        for item in manifest:
            self.__setattr__(item, "")
    
    def __setitem__(self,key,value):
        self.__setattr__(key,value)
    
    def __getitem__(self,key):
        self.__getattribute__(key)
    
    def manifest_output(self):
        return [self.__getattribute__(x) for x in self.manifest]


CAR_SLOW_SPEED = 25
class CarProcessor():
    def __init__(self,driver_proc=None, current_ir=None, manifest=CarsManifest) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.driver_proc = driver_proc
        self.lookup = {}
        self.prev_dist_pct = []
        self.prev_time = current_ir['SessionTime']
        self.sectors = current_ir['SplitTimeInfo']['Sectors'];
        self.manifest = manifest + [f's{x+1}' for x in range(len(self.sectors))]
        
        self.overall_best_sectors = [sys.maxsize for x in range(len(self.sectors))]
        self.overall_best_lap = sys.maxsize
        self.class_best_laps = [] # todo!

        milesInKm = 1.60934
        m = re.search(r'(?P<length>(\d+\.\d+)) (?P<unit>(km|mi))', current_ir['WeekendInfo']['TrackLength']) 
        if (m.group('unit') == 'mi'):
            self.track_length = float(m.group('length')) * milesInKm * 1000;
        else:
            self.track_length =  float(m.group('length')) * 1000
        print(f"TrackLength: {self.track_length}")
        self.min_move_dist_pct = 0.1/self.track_length # if a car doesn't move 10cm in 1/60s 
        self.last_standings = current_ir['SessionInfo']['Sessions'][current_ir['SessionNum']]['ResultsPositions']
        self.speedmap = SpeedMap(self.track_length)


    def process(self,ir,msg_proc):
        for idx in range(64):     
            if idx == ir['DriverInfo']['PaceCarIdx']:
                continue
            if  ir['CarIdxLapDistPct'][idx] > -1:                
                if idx not in self.lookup.keys():
                    work = CarData(self.manifest, len(self.sectors))
                    work['last'] = -1
                    work['best'] = -1
                    self.lookup[idx] = work
                else:
                    work = self.lookup.get(idx)
                work['state'] = 'RUN'
                work['carIdx'] = idx
                work['carNum'] = self.driver_proc.car_number(idx)
                work['userName'] = self.driver_proc.user_name(idx)
                work['teamName'] = self.driver_proc.team_name(idx)
                work['carClass'] = self.driver_proc.car_class(idx)
                work['pos'] = ir['CarIdxPosition'][idx]
                work['pic'] = ir['CarIdxClassPosition'][idx]
                work['lap'] = ir['CarIdxLap'][idx]
                work['lc'] = ir['CarIdxLapCompleted'][idx]
                work['dist'] = 0                
                work['interval'] = 0
                work['trackPos'] = gate(ir['CarIdxLapDistPct'][idx])
                # work['last'] = ir['CarIdxLastLapTime'][idx]
                # work['best'] = ir['CarIdxBestLapTime'][idx]      
                
                self.compute_times(work,ir, msg_proc)

                speed = self.calc_speed(ir, idx)
                work['speed'] = speed
                if ir['CarIdxOnPitRoad'][idx]:
                    work['state'] = 'PIT'                    
                if ir['CarIdxRPM'][idx] == -1:
                    work['state'] = 'OUT'                    
                elif speed > 0 and speed < CAR_SLOW_SPEED and not ir['CarIdxOnPitRoad'][idx]:
                    work['state'] = 'SLOW'                    
                    if work.slow_marker == False:
                        msg_proc.add_car_slow(idx,speed)
                        work.slow_marker = True
                if speed > CAR_SLOW_SPEED:
                    work.slow_marker = False
                    

            else:
                # handle those cars which have an entry in driver but do not appear valid in CarIdxLapDistPct
                # these cars may be out of the race...
                pass
        self.calc_delta(ir)
        cur_standings = ir['SessionInfo']['Sessions'][ir['SessionNum']]['ResultsPositions']
        if (cur_standings) != self.last_standings:
            self.process_standings(cur_standings,msg_proc)

        self.prev_dist_pct = ir['CarIdxLapDistPct'][:] # create a copy for next run
        self.prev_time = ir['SessionTime']

    def process_standings(self, st, msg_proc):
        # Note: we get the standings a little bit after a car crossed the line (about a second)
        # 
        if (st == None):
            return
        self.logger.debug(f"new standings arrived")
        for line in st:
            work = self.lookup.get(line['CarIdx'])
            work['pos'] = line['Position']
            work['pic'] = line['ClassPosition']
            work['gap'] = line['Time']
            work['best'] = line['FastestTime']
            duration = line['LastTime']
            if duration == -1:
                duration = work.lap_timings.lap.duration
                work['last'] = duration
            else:
                if duration < self.overall_best_lap:
                    work['last'] = [duration, "ob"]                    
                    self.overall_best_lap = duration
                    msg_proc.add_timing_info(line['CarIdx'], f'new overall best lap {laptimeStr(duration)}')

                elif duration == line['FastestTime']:
                    work['last'] = [duration, "pb"]                    
                    msg_proc.add_timing_info(line['CarIdx'], f'personal new best lap {laptimeStr(duration)}')
                else:
                    work['last'] = duration
                    
        self.last_standings = st


    def compute_times(self, carData, ir, msg_proc):
        trackPos = getattr(carData, 'trackPos')
        car_idx = getattr(carData, 'carIdx')
        i = len(self.sectors)-1        
        while trackPos < self.sectors[i]['SectorStartPct']:
            i = i - 1
        # i holds the current sector
        if carData.current_sector == -1:
            carData.current_sector = i
            # don't compute this sector. on -1 we are pretty much rushing into a running race or just put into the car
            return 
                
        if i == carData.current_sector:
            return
        
        # use this for debugging
        car_num = self.driver_proc.car_number(getattr(carData, 'carIdx'))

        # the prev sector is done (we assume the car is running in the correct direction)
        # but some strange things may happen: car spins, comes to a halt, drives in reverse direction and crosses the sector mark multiple times ;)
        # very rare, I hope
        # so we check if the current sector is the next "expected" sector
        expected_sector = (carData.current_sector + 1) % len(self.sectors)
        if i != expected_sector:
            # current sector does not match the expected next sector
            # self.logger.warn(f"car {car_num} not in expected sector. got value: {i} expect: {expected_sector}")
            return
        
        t = ir['SessionTime']
        # close the (now) previous sector        
        sector = carData.lap_timings.sectors[carData.current_sector]
        
        # if the sector has no start time we ignore it. prepare the next one and leave 
        if sector.start_time == -1:
            carData.current_sector = i
            sector = carData.lap_timings.sectors[i]
            sector.mark_start(t)
            return

        duration = sector.mark_stop(t)
        # handle the colors for best sector
        if duration < self.overall_best_sectors[carData.current_sector]:
            setattr(carData, f's{carData.current_sector+1}', [duration, "ob"])
            self.overall_best_sectors[carData.current_sector] = duration
            # TODO: if another car has also an "ob" sector, downgrade it to "pb" or "cb" ;)
            sector.best = duration
        elif duration < sector.best:
            setattr(carData, f's{carData.current_sector+1}', [duration, "pb"])
            sector.best = duration
        else:
            setattr(carData, f's{carData.current_sector+1}', sector.duration)
        
        # mark all sectors after this as old if first sector is done
        if carData.current_sector == 0:
            for x in range(i, len(self.sectors)):
                setattr(carData, f's{x+1}', [carData.lap_timings.sectors[x].duration, "old"])

        carData.current_sector = i
        # start the new current sector
        sector = carData.lap_timings.sectors[i]
        sector.mark_start(t)

        # compute own laptime
        if (i == 0):            
            self.logger.info(f"car {car_num} crossed the line")
                                    
            if carData.lap_timings.lap.start_time == -1:
                self.logger.info(f"car {car_num} had start_time of -1. not recording this one")
            else:
                duration = carData.lap_timings.lap.mark_stop(t)

            carData.lap_timings.lap.mark_start(t)


    def parkplatz(self):
        # do not call!
        if duration == -1:
            self.logger.info(f"car {car_num} -1 laptime reported by iR. using own lap time")
            if carData.lap_timings.lap.start_time == -1:
                self.logger.info(f"car {car_num} had start_time of -1. not recording this one")
            else:
                duration = carData.lap_timings.lap.mark_stop(t)

        if duration < self.overall_best_lap:
            setattr(carData, f'last', [duration, "ob"])
            carData.lap_timings.lap.best = duration
            self.overall_best_lap = duration
            msg_proc.add_timing_info(car_idx, f'new overall best lap {laptimeStr(duration)}')

        elif duration < carData.lap_timings.lap.best:
            setattr(carData, f'last', [duration, "pb"])
            carData.lap_timings.lap.best = duration
            msg_proc.add_timing_info(car_idx, f'new personal best lap {laptimeStr(duration)}')
    
    def race_starts(self, ir):
        pass






        
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
            else:
                if ir['CarIdxOnPitRoad'][idx] == False and speed > 0:
                    car_class_id = self.driver_proc.car_class_id(idx)                    
                    self.speedmap.process(current_dist, speed, idx, car_class_id)
            return speed
        else:
            return 0
    
    def calc_delta(self, ir):

        current_race_order = [(i.carIdx, i.lap+i.trackPos)  for i in self.lookup.values()]
        current_race_order.sort(key = lambda k: k[1], reverse=True)
        #ordered = [self.lookup[item[0]] for item in current_race_order]

        # current_race_order = [(i, ir['CarIdxLap'][i]+ir['CarIdxLapDistPct'][i])  for i in range(0,64)]
        # current_race_order.sort(key = lambda k: k[1], reverse=True)
        session_num = ir['SessionNum']
        if ir['SessionInfo']['Sessions'][session_num]['SessionType'] != 'Race':
            return
        
        current_pct = ir['CarIdxLapDistPct']
        for i in range(1, len(current_race_order)):          
            item = current_race_order[i]                  
            if (item[1] < 0):
                continue
            work = self.lookup[item[0]]

            car_in_front_pos = current_pct[current_race_order[i-1][0]]
            current_car_pos = current_pct[item[0]]
            # data.car_idx_dist_meters[item[0]] =  delta_distance(gate(current_pct[current_race_order[i-1][0]]), gate(current_pct[item[0]])) * self.track_length            
            work['dist'] =  delta_distance(gate(current_pct[current_race_order[i-1][0]]), gate(current_pct[item[0]])) * self.track_length            
            if getattr(work,'speed') <= 0:
                work['interval'] = 999
            else:
                # x1 = filter(lambda x: x['CarIdx']==i, state.lastDI['Drivers'])
                # y = next(x1)
                for d in ir['DriverInfo']['Drivers']:
                    if d['CarIdx'] == i:
                        car_class_id = d['CarClassID']
                        if self.speedmap != None:
                            delta_by_car_class_speedmap = self.speedmap.compute_delta_time(car_class_id, car_in_front_pos, current_car_pos)
                            work['interval'] = delta_by_car_class_speedmap
                        else:
                            work['interval'] = 999

    def manifest_output(self):
        
        current_race_order = [(i.carIdx, i.lap+i.trackPos)  for i in self.lookup.values()]
        current_race_order.sort(key = lambda k: k[1], reverse=True)
        ordered = [self.lookup[item[0]] for item in current_race_order]
        return [[getattr(m, x) for x in self.manifest] for m in ordered]
        
        
        
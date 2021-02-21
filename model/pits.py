PitInfoManifest = ['carNum', 'type', 'enterTime', 'exitTime', 'laneTime', 'stintTime', 'lapEnter', 'lapExit']    

class PitStopInfo:
    def __init__(self, carIdx=-1) -> None:
        self.car_idx = carIdx
        self.enter_time = -1
        self.exit_time = -1
        self.driving_time = -1
        self.pit_lane_time = -1
        self.lap_enter = -1
        self.lap_exit = -1


class PitProcessor():
    def __init__(self, current_ir, msg_proc, driver_proc) -> None:
        self.last_ir_pit_status = current_ir['CarIdxOnPitRoad']
        self.msg_proc = msg_proc
        self.driver_proc = driver_proc
        self.send_buffer = []
        self.lookup = {}
        for idx in range(64):
            self.lookup[idx] = PitStopInfo(carIdx = idx)

    def clear_buffer(self):
        self.send_buffer.clear()

    def race_starts(self, ir):
        for item in self.lookup.values():
            item.exit_time = ir['SessionTime']
            item.lap_exit = ir['CarIdxLap'][item.car_idx]

    def process(self, ir):        
        for idx in range(64):            
            if idx == ir['DriverInfo']['PaceCarIdx']:
                continue
            if  ir['CarIdxLapDistPct'][idx] > -1:
                current = ir['CarIdxOnPitRoad'][idx]
                if current != self.last_ir_pit_status[idx]:
                    pit_info = self.lookup[idx]                                        
                    if current:
                        pit_info.lap_enter = ir['CarIdxLap'][idx]
                        pit_info.enter_time = ir['SessionTime']                       
                        pit_info.driving_time = pit_info.enter_time - pit_info.exit_time
                        self.msg_proc.add_pit_enter_msg(pit_info)
                        self.send_buffer.append({
                            'carNum':self.driver_proc.car_number(idx),
                            'type':'enter',
                            'enterTime': pit_info.enter_time,
                            'exitTime': '',
                            'laneTime': '',
                            'stintTime': pit_info.driving_time,
                            'lapEnter': pit_info.lap_enter,
                            'lapExit': ''
                            })
                    else:
                        pit_info.lap_exit = ir['CarIdxLap'][idx]
                        pit_info.exit_time = ir['SessionTime']                        
                        pit_info.pit_lane_time = pit_info.exit_time - pit_info.enter_time
                        self.msg_proc.add_pit_exit_msg(pit_info)
                        self.send_buffer.append({
                            'carNum':self.driver_proc.car_number(idx),
                            'type':'exit',
                            'enterTime': '',
                            'exitTime': pit_info.exit_time,
                            'laneTime': pit_info.pit_lane_time,
                            'stintTime': '',
                            'lapEnter': '',
                            'lapExit': pit_info.lap_exit,
                            })
                    

        self.last_ir_pit_status = ir['CarIdxOnPitRoad']
    
    def manifest_output(self):        
        return [[m[x] for x in PitInfoManifest] for m in self.send_buffer]

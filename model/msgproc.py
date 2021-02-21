from .pits import PitStopInfo

MessagesManifest = ['type', 'subType', 'carIdx','carNum', 'carClass', 'msg']    

class MessageProcessor:
    def __init__(self, drivers) -> None:
        self.msg_buffer = []        
        self.drivers = drivers

    def clear_buffer(self):
        self.msg_buffer.clear()

    def add_pit_enter_msg(self, pitinfo):        
        self.msg_buffer.append({
            'type': 'Pits',
            'subType':'Enter',
            'carIdx': pitinfo.car_idx, 
            'carNum': self.drivers.car_number(pitinfo.car_idx), 
            'carClass': self.drivers.car_class(pitinfo.car_idx), 
            'msg': f'#{self.drivers.car_number(pitinfo.car_idx)} ({self.drivers.user_name(pitinfo.car_idx)}) entered pitlane'})

    def add_pit_exit_msg(self, pitinfo):        
        self.msg_buffer.append({
            'type': 'Pits',
            'subType':'Exit',
            'carIdx': pitinfo.car_idx, 
            'carNum': self.drivers.car_number(pitinfo.car_idx), 
            'carClass': self.drivers.car_class(pitinfo.car_idx), 
            'msg': f'#{self.drivers.car_number(pitinfo.car_idx)} ({self.drivers.user_name(pitinfo.car_idx)}) exited pitlane'})

    def manifest_output(self):
        return [[m[x] for x in MessagesManifest] for m in self.msg_buffer]
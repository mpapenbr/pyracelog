class DriverProcessor():
    def __init__(self, current_ir=None) -> None:
        self.lookup = {}
        for d in current_ir['DriverInfo']['Drivers']:
            self.lookup[d['CarIdx']] = d.copy()

    def process(self, ir):
        # TODO: detect changes in ir-drivers.
        pass

    def car_class(self, car_idx):
        return self.lookup[car_idx]['CarClassShortName']
    def car_number(self, car_idx):
        return self.lookup[car_idx]['CarNumber']
    def car_num_raw(self, car_idx):
        return self.lookup[car_idx]['CarNumberRaw']
    def user_name(self, car_idx):
        return self.lookup[car_idx]['UserName']
    def team_name(self, car_idx):
        return self.lookup[car_idx]['TeamName']

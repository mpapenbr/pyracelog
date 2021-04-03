import unittest
import irsdk

class RaceState:
    def __init__(self, init_state=0) -> None:
        self.state = init_state
        self.stateSwitcher = {
            irsdk.SessionState.invalid: self.s_invalid,
            irsdk.SessionState.racing: self.s_racing,
            irsdk.SessionState.checkered: self.s_checkered
        }
    
    def s_invalid(self, args):
        if (args == "green"):
            self.state = irsdk.SessionState.racing
        
    def s_racing(self, args):
        if (args == "checkered"):
            self.state = irsdk.SessionState.checkered

    def s_checkered(self, args):
        pass
        
    
    def tick(self, args):        
        self.stateSwitcher[self.state](args)
        

class TestState(unittest.TestCase):
    def test_x(self):
        raceState = RaceState(irsdk.SessionState.invalid)
        raceState.tick("something")
        self.assertEqual(raceState.state,irsdk.SessionState.invalid)
        raceState.tick("green")
        self.assertEqual(raceState.state,irsdk.SessionState.racing)
        raceState.tick("green")
        self.assertEqual(raceState.state,irsdk.SessionState.racing)
        raceState.tick("checkered")
        self.assertEqual(raceState.state,irsdk.SessionState.checkered)
        
        

    def test_dummy(self):
        self.assertTrue(1==1)
        

        

if __name__ == '__main__':
    unittest.main()
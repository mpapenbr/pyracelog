import unittest

class DataSet():
    def __init__(self, spec, data=[]):
        super().__init__()
        self.spec = spec;
        for i, item in enumerate(spec):
            if (item[1] == "text"):
                setattr(self, item[0], data[i])
            if (item[1] == "numeric"):
                setattr(self, item[0], data[i])
        

class TestDataType(unittest.TestCase):
    def test_manifest(self):
        spec = [["c1","text", "XX",], ["n", "numeric", "YY"]]
        data = [["a",1],["c",2]]
        d = DataSet(spec, data[0])
        self.assertEqual(d.c1, "a")
        self.assertEqual(d.n, 1)
        

    def test_dummy(self):
        self.assertTrue(1==1)
        

        

if __name__ == '__main__':
    unittest.main()
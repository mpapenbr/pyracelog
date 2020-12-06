
sectors = [{'bla':0}, {'bla':0},{'bla':1, 'CarIdx': 388}]

def find_sector(cur:float) -> int:
    i = len(sectors)-1    
    while cur < sectors[i]:
        i = i - 1
    return i

x = [value for value in sectors if value['bla'] == 1]
carIdx = x[0]['CarIdx']
print(f'{x[0]} - {carIdx}')

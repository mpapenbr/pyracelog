def gate(v):
    if v < 0:
        return 0
    if v > 1:
        return 1
    return v

def delta(a,b):
    if a >= b:
        return a-b
    else:
        return a+1-b

p1 = 1
p2 = 1.003
p3 = 0.999
p4 = 0.001
p5 = -0.001

print(f'pure p2,p1: {delta(p2,p1):.4f}')        
print(f'gate p1,p1: {delta(gate(p1),gate(p1)):.4f}')        
print(f'gate p1,p2: {delta(gate(p1),gate(p2)):.4f}')        
print(f'gate p1,p2: {delta(gate(p1),gate(p2)):.4f}')        
print(f'gate p2,p2: {delta(gate(p2),gate(p2)):.4f}')        
print(f'gate p4,p3: {delta(gate(p4),gate(p3)):.4f}')        
print(f'gate p3,p4: {delta(gate(p3),gate(p4)):.4f}')        
print(f'gate p4,p5: {delta(gate(p4),gate(p5)):.4f}')        
print(f'gate p2,p5: {delta(gate(p2),gate(p5)):.4f}')        
print(f'gate p5,p2: {delta(gate(p5),gate(p2)):.4f}')        
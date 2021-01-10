# pyracelog

This tool extracts telemetry data from iRacing using the pyirsdk module (see https://github.com/kutu/pyirsdk)

The idea behind this tool is to extract race data every second and send them to a backend.

The backend should further process the data in order to provide further analysis data. The focus is on lap times and pit stops for endurance races.


## Notes

Certain data is needed before we can start the processing
1. track_length
  available via WeekendInfo. This is needed for the SpeedMap
0. When the loop starts these infos must be ready  
    - SpeedMap  
      Needed for computation of delta times  
    - Driver data  
      needed to get the CarClassID for a driver (which in turn is required for the SpeedMap)
    - Split sectors  

### When a new session starts

This occurs if `ir['SessionUniqueID']` changes. This will also detect session resets (available in AI sessions)


Actions:
- reset all laptimes
- reset all pitstops
- reset SpeedMap


### When to compute deltas?
Delta times only make sense in race sessions. These are called **RACE** or **HEAT***NUM*

### Which (own) laptimes should be considered invalid
- they do not contain all sectors
- they are way below a meaningful laptime

Problems:
- car resets
- connection issues 
- iraing telemetry issues (when certain vars are set to values which disturb our computations)
## Caveats

### Using replay in iRacing
When using the replay function in iRacing at least the following attributes gets -1 

- car_idx_position
- car_idx_class_position

### Driver gets a slow down
car_idx_lap may be -1

## Delta times

By now they are just functioning as a placeholder since their value is not based on the correct/meaningful speed.

David Tucker made a proposal here: https://members.iracing.com/jforum/posts/list/3525/1470675.page#12081878
In short:
- divide the track in multpiple short chunks (10 meters for example)
- measure the min/max/avg speed for every car in those chunks
- when calculating the delta, use those chunk values.
- Issues to solve:
  - what to do when we have no history?
    - first lap
    
# Resources
[1] Telemetry variables https://members.iracing.com/jforum/posts/list/3400/1470675.page#12019603



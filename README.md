# pyracelog

This tool extracts telemetry data from iRacing using the pyirsdk module (see https://github.com/kutu/pyirsdk)

The idea behind this tool is to extract race data every second and send them to a backend.

The backend should further process the data in order to provide further analysis data. The focus is on lap times and pit stops for endurance races.


## Caveats

When using the replay function in iRacing at least the following attributes gets -1 

- car_idx_position
- car_idx_class_position
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



# pyracelog

This tool extracts telemetry data from iRacing using the pyirsdk module (see https://github.com/kutu/pyirsdk)

The idea behind this tool is to extract race data every second and send them to a backend.

The backend should further process the data in order to provide further analysis data. The focus is on lap times and pit stops for endurance races.
# Data transfer

Every second new data should be send to the server. We are only interested in race data so any other session than race is not relevant here.

*Note*: to deal with heat races is tbd.

## What is considered to be new data
- all defined car_idx* arrays
- session* in DataStore
- changes in ir[DriverInfo][Drivers] 
  We should really detect changes in the list and transfer only the changes
- changes in ir[SessionInfo][Sessions][:-1][ResultPositions]  
  - if we detect changes we transfer the complete ResultPositions array
  - the laptime in ResultPositions has always priority. In case there is no laptime we put our own computed laptime in.
  - 

- new sector times
- new pit stops


## Debugging/Monitoring

Let an react-app connect to this application via websocket. We could send the same data to the websocket that we would send to the server.




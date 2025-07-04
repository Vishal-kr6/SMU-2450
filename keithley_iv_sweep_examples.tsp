--[[

Example Configuration for Keithley 2450 I-V Sweep TSP Script

This file demonstrates different parameter configurations for the 
keithley_iv_sweep.tsp script. Copy and modify the parameters below,
then paste them at the top of the main TSP script before running.

]]

-- Example 1: Basic voltage sweep for diode characterization
--[[
local sweep_mode = "VOLT"              
local four_wire_sensing = false        
local terminal_location = "FRONT"      
local measure_resistance = false       
local nplc = 1.0                      
local measurement_delay = 0.01        
local num_cycles = 1                  
local start_voltage = 0.0             
local stop_voltage = 1.0              
local step_voltage = 0.01             
local current_limit = 0.1             
local start_current = 0.0             
local stop_current = 0.01             
local step_current = 0.0005           
local voltage_limit = 5.0             
]]

-- Example 2: High precision resistance measurement (4-wire)
--[[
local sweep_mode = "CURR"              
local four_wire_sensing = true         
local terminal_location = "REAR"       
local measure_resistance = true        
local nplc = 10.0                     
local measurement_delay = 0.1         
local num_cycles = 3                  
local start_voltage = 0.0             
local stop_voltage = 1.0              
local step_voltage = 0.01             
local current_limit = 0.01            
local start_current = -0.01           
local stop_current = 0.01             
local step_current = 0.001            
local voltage_limit = 1.0             
]]

-- Example 3: Fast voltage sweep with multiple cycles
--[[
local sweep_mode = "VOLT"              
local four_wire_sensing = false        
local terminal_location = "FRONT"      
local measure_resistance = true        
local nplc = 0.1                      
local measurement_delay = 0.005       
local num_cycles = 5                  
local start_voltage = -2.0            
local stop_voltage = 2.0              
local step_voltage = 0.1              
local current_limit = 0.05            
local start_current = 0.0             
local stop_current = 0.01             
local step_current = 0.0005           
local voltage_limit = 5.0             
]]

-- Example 4: Low current measurement
--[[
local sweep_mode = "VOLT"              
local four_wire_sensing = true         
local terminal_location = "REAR"       
local measure_resistance = false       
local nplc = 5.0                      
local measurement_delay = 0.05        
local num_cycles = 1                  
local start_voltage = 0.0             
local stop_voltage = 10.0             
local step_voltage = 0.5              
local current_limit = 1e-6            
local start_current = 0.0             
local stop_current = 0.01             
local step_current = 0.0005           
local voltage_limit = 5.0             
]]

print("Example configurations loaded. Copy the desired configuration to the main TSP script.")
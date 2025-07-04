--[[

***********************************************************
*** Keithley 2450 I-V Sweep TSP Script                 ***
*** Converted from Python GUI Application              ***
***********************************************************

Description: This TSP script performs I-V characteristic measurements
on the Keithley 2450 SMU. It supports both voltage and current sweep
modes with configurable parameters including multiple cycles, 4-wire
sensing, and resistance calculations.

Features:
- Voltage sweep: sweeps voltage and measures current
- Current sweep: sweeps current and measures voltage  
- Multiple measurement cycles
- 2-wire or 4-wire sensing
- Front or rear terminal selection
- Configurable NPLC and measurement delay
- Progress tracking with print statements
- Automatic resistance calculation (when enabled)
- Safe output control with error handling
- Data buffer management

]]

-- ====================================================================
-- CONFIGURATION PARAMETERS
-- ====================================================================
-- Modify these parameters before loading the script to the instrument

-- Sweep configuration
local sweep_mode = "VOLT"              -- "VOLT" for voltage sweep, "CURR" for current sweep
local four_wire_sensing = true         -- true for 4-wire, false for 2-wire sensing
local terminal_location = "FRONT"      -- "FRONT" or "REAR"
local measure_resistance = true        -- true to calculate and display resistance

-- Timing parameters
local nplc = 1.0                      -- Number of power line cycles (0.01 to 10)
local measurement_delay = 0.05        -- Delay between measurements in seconds
local num_cycles = 3                  -- Number of measurement cycles to perform

-- Voltage sweep parameters (used when sweep_mode = "VOLT")
local start_voltage = 0.0             -- Start voltage in volts
local stop_voltage = 1.0              -- Stop voltage in volts  
local step_voltage = 0.01             -- Step voltage in volts
local current_limit = 0.01            -- Current limit in amperes

-- Current sweep parameters (used when sweep_mode = "CURR")
local start_current = 0.0             -- Start current in amperes
local stop_current = 0.01             -- Stop current in amperes
local step_current = 0.0005           -- Step current in amperes
local voltage_limit = 5.0             -- Voltage limit in volts

-- ====================================================================
-- HELPER FUNCTIONS
-- ====================================================================

-- Function to validate sweep parameters
local function validate_parameters()
    print("Validating sweep parameters...")
    
    -- Check sweep mode
    if sweep_mode ~= "VOLT" and sweep_mode ~= "CURR" then
        error("Invalid sweep_mode. Must be 'VOLT' or 'CURR'")
    end
    
    -- Check terminal location
    if terminal_location ~= "FRONT" and terminal_location ~= "REAR" then
        error("Invalid terminal_location. Must be 'FRONT' or 'REAR'")
    end
    
    -- Check step values are not zero
    if sweep_mode == "VOLT" then
        if step_voltage == 0 then
            error("Step voltage cannot be zero")
        end
        if math.abs(stop_voltage - start_voltage) < math.abs(step_voltage) then
            error("Invalid voltage sweep range: step size too large")
        end
    else
        if step_current == 0 then
            error("Step current cannot be zero")
        end
        if math.abs(stop_current - start_current) < math.abs(step_current) then
            error("Invalid current sweep range: step size too large")
        end
    end
    
    -- Check NPLC range
    if nplc < 0.01 or nplc > 10 then
        error("NPLC must be between 0.01 and 10")
    end
    
    -- Check number of cycles
    if num_cycles < 1 then
        error("Number of cycles must be at least 1")
    end
    
    print("Parameter validation passed")
end

-- Function to configure instrument settings
local function configure_instrument()
    print("Configuring instrument...")
    
    -- Reset and clear instrument
    reset()
    defbuffer1.clear()
    
    -- Set terminal location
    if terminal_location == "FRONT" then
        smu.terminals = smu.TERMINALS_FRONT
    else
        smu.terminals = smu.TERMINALS_REAR
    end
    
    -- Configure sensing mode
    if four_wire_sensing then
        smu.measure.sense = smu.SENSE_4WIRE
        print("Configured for 4-wire sensing")
    else
        smu.measure.sense = smu.SENSE_2WIRE
        print("Configured for 2-wire sensing")
    end
    
    -- Configure source and measure functions based on sweep mode
    if sweep_mode == "VOLT" then
        smu.source.func = smu.FUNC_DC_VOLTAGE
        smu.measure.func = smu.FUNC_DC_CURRENT
        smu.source.ilimit.level = current_limit
        print(string.format("Voltage sweep mode: %g V to %g V, step %g V, current limit %g A", 
              start_voltage, stop_voltage, step_voltage, current_limit))
    else
        smu.source.func = smu.FUNC_DC_CURRENT
        smu.measure.func = smu.FUNC_DC_VOLTAGE
        smu.source.vlimit.level = voltage_limit
        print(string.format("Current sweep mode: %g A to %g A, step %g A, voltage limit %g V", 
              start_current, stop_current, step_current, voltage_limit))
    end
    
    -- Set measurement parameters
    smu.source.autorange = smu.ON
    smu.measure.autorange = smu.ON
    smu.measure.nplc = nplc
    
    -- Configure buffer to collect timestamps
    defbuffer1.collecttimestamps = 1
    
    print(string.format("NPLC: %g, Measurement delay: %g s", nplc, measurement_delay))
    print("Instrument configuration complete")
end

-- Function to calculate number of points in sweep
local function calculate_sweep_points()
    local points
    if sweep_mode == "VOLT" then
        points = math.floor(math.abs(stop_voltage - start_voltage) / math.abs(step_voltage)) + 1
    else
        points = math.floor(math.abs(stop_current - start_current) / math.abs(step_current)) + 1
    end
    return points
end

-- Function to perform a single sweep cycle
local function perform_sweep_cycle(cycle_num)
    print(string.format("Starting sweep cycle %d of %d", cycle_num, num_cycles))
    
    local cycle_start_index = defbuffer1.n + 1
    
    -- Turn on output
    smu.source.output = smu.ON
    print("Output enabled")
    
    -- Perform sweep
    local point_count = 0
    local total_points = calculate_sweep_points()
    
    if sweep_mode == "VOLT" then
        -- Voltage sweep
        local voltage_step = step_voltage
        if stop_voltage < start_voltage then
            voltage_step = -math.abs(step_voltage)
        end
        
        for v = start_voltage, stop_voltage, voltage_step do
            smu.source.level = v
            delay(measurement_delay)
            smu.measure.read(defbuffer1)
            point_count = point_count + 1
            
            -- Progress indicator every 10% of points
            if point_count % math.max(1, math.floor(total_points / 10)) == 0 then
                print(string.format("Cycle %d: %d%% complete (%d/%d points)", 
                      cycle_num, math.floor(point_count * 100 / total_points), point_count, total_points))
            end
        end
    else
        -- Current sweep
        local current_step = step_current
        if stop_current < start_current then
            current_step = -math.abs(step_current)
        end
        
        for i = start_current, stop_current, current_step do
            smu.source.level = i
            delay(measurement_delay)
            smu.measure.read(defbuffer1)
            point_count = point_count + 1
            
            -- Progress indicator every 10% of points
            if point_count % math.max(1, math.floor(total_points / 10)) == 0 then
                print(string.format("Cycle %d: %d%% complete (%d/%d points)", 
                      cycle_num, math.floor(point_count * 100 / total_points), point_count, total_points))
            end
        end
    end
    
    -- Turn off output
    smu.source.output = smu.OFF
    print("Output disabled")
    
    local cycle_end_index = defbuffer1.n
    print(string.format("Cycle %d complete: %d measurements taken", cycle_num, cycle_end_index - cycle_start_index + 1))
    
    return cycle_start_index, cycle_end_index
end

-- Function to display measurement results
local function display_results()
    print("\n" .. string.rep("=", 60))
    print("MEASUREMENT RESULTS")
    print(string.rep("=", 60))
    
    if defbuffer1.n == 0 then
        print("No measurements in buffer")
        return
    end
    
    print(string.format("Total measurements: %d", defbuffer1.n))
    print(string.format("Measurement time span: %.3f seconds", 
          defbuffer1.relativetimestamps[defbuffer1.n] - defbuffer1.relativetimestamps[1]))
    
    -- Print column headers
    if measure_resistance then
        if sweep_mode == "VOLT" then
            print("Voltage (V)\tCurrent (A)\tResistance (Ω)\tTime (s)")
        else
            print("Current (A)\tVoltage (V)\tResistance (Ω)\tTime (s)")
        end
    else
        if sweep_mode == "VOLT" then
            print("Voltage (V)\tCurrent (A)\tTime (s)")
        else
            print("Current (A)\tVoltage (V)\tTime (s)")
        end
    end
    
    -- Print measurement data
    for i = 1, defbuffer1.n do
        local source_val = defbuffer1.sourcevalues[i]
        local reading = defbuffer1.readings[i]
        local timestamp = defbuffer1.relativetimestamps[i]
        
        if measure_resistance then
            local resistance
            if sweep_mode == "VOLT" then
                -- V sweep: resistance = V/I
                resistance = (reading ~= 0) and (source_val / reading) or math.huge
            else
                -- I sweep: resistance = V/I  
                resistance = (source_val ~= 0) and (reading / source_val) or math.huge
            end
            
            print(string.format("%.6g\t%.6g\t%.6g\t%.3f", 
                  source_val, reading, resistance, timestamp))
        else
            print(string.format("%.6g\t%.6g\t%.3f", 
                  source_val, reading, timestamp))
        end
    end
end

-- Function to print summary statistics
local function print_summary()
    print("\n" .. string.rep("=", 60))
    print("SUMMARY STATISTICS")
    print(string.rep("=", 60))
    
    if defbuffer1.n == 0 then
        return
    end
    
    -- Calculate statistics
    local min_reading = math.huge
    local max_reading = -math.huge
    local sum_reading = 0
    
    for i = 1, defbuffer1.n do
        local reading = defbuffer1.readings[i]
        min_reading = math.min(min_reading, reading)
        max_reading = math.max(max_reading, reading)
        sum_reading = sum_reading + reading
    end
    
    local avg_reading = sum_reading / defbuffer1.n
    
    if sweep_mode == "VOLT" then
        print(string.format("Current statistics:"))
        print(string.format("  Minimum: %.6g A", min_reading))
        print(string.format("  Maximum: %.6g A", max_reading))
        print(string.format("  Average: %.6g A", avg_reading))
    else
        print(string.format("Voltage statistics:"))
        print(string.format("  Minimum: %.6g V", min_reading))
        print(string.format("  Maximum: %.6g V", max_reading))
        print(string.format("  Average: %.6g V", avg_reading))
    end
end

-- Function for safe cleanup on error
local function safe_cleanup()
    print("Performing safety cleanup...")
    
    -- Turn off output
    if smu.source.output == smu.ON then
        smu.source.output = smu.OFF
        print("Output turned off")
    end
    
    -- Set source level to zero
    smu.source.level = 0
    print("Source level set to zero")
end

-- ====================================================================
-- MAIN EXECUTION FUNCTION
-- ====================================================================

local function main()
    print("Keithley 2450 I-V Sweep Script Starting...")
    print(string.format("Script version: %s", os.date("%Y%m%d")))
    
    local success, error_msg = pcall(function()
        -- Validate parameters
        validate_parameters()
        
        -- Configure instrument
        configure_instrument()
        
        -- Calculate and display sweep information
        local total_points = calculate_sweep_points()
        local total_measurements = total_points * num_cycles
        
        print(string.format("Sweep configuration: %d points per cycle, %d cycles, %d total measurements", 
              total_points, num_cycles, total_measurements))
        
        -- Estimate measurement time
        local estimated_time = total_measurements * (measurement_delay + 0.01) -- 10ms overhead per measurement
        print(string.format("Estimated measurement time: %.1f seconds", estimated_time))
        
        print("\nStarting measurements...")
        local overall_start_time = os.clock()
        
        -- Perform measurement cycles
        for cycle = 1, num_cycles do
            local cycle_start, cycle_end = perform_sweep_cycle(cycle)
            
            -- Brief delay between cycles
            if cycle < num_cycles then
                delay(0.1)
            end
        end
        
        local overall_end_time = os.clock()
        local actual_time = overall_end_time - overall_start_time
        
        print(string.format("\nAll measurements complete in %.1f seconds", actual_time))
        
        -- Display results and statistics
        display_results()
        print_summary()
        
        print("\nI-V sweep completed successfully!")
    end)
    
    if not success then
        print(string.format("ERROR: %s", error_msg))
        safe_cleanup()
        error(error_msg)
    end
end

-- ====================================================================
-- SCRIPT EXECUTION
-- ====================================================================

-- Check if this script is being run directly or loaded as a module
if not pcall(debug.getlocal, 4, 1) then
    -- Script is being run directly, execute main function
    main()
else
    -- Script is being loaded as a module, just define functions
    print("I-V Sweep script loaded as module. Call main() to execute.")
end
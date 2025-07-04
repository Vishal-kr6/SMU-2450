#!/usr/bin/env python3
"""
Example script showing how to load and execute the TSP I-V sweep script
on a Keithley 2450 instrument using PyVISA.

This demonstrates the complete workflow from parameter configuration
to script execution and data retrieval.
"""

import time
import os

try:
    import pyvisa
    PYVISA_AVAILABLE = True
except ImportError:
    PYVISA_AVAILABLE = False
    print("Note: PyVISA not available in this environment. This is a demonstration only.")

def find_keithley_2450():
    """Find and connect to a Keithley 2450 instrument."""
    if not PYVISA_AVAILABLE:
        print("PyVISA not available - cannot connect to instruments")
        return None
        
    rm = pyvisa.ResourceManager()
    resources = rm.list_resources()
    
    for resource in resources:
        if "USB" in resource or "TCPIP" in resource:
            try:
                inst = rm.open_resource(resource)
                inst.timeout = 10000  # 10 second timeout
                idn = inst.query("*IDN?")
                if "2450" in idn:
                    print(f"Found Keithley 2450: {idn.strip()}")
                    return inst
                else:
                    inst.close()
            except Exception as e:
                print(f"Could not connect to {resource}: {e}")
                continue
    
    return None

def customize_tsp_parameters(sweep_type="voltage_sweep_demo"):
    """
    Customize TSP script parameters for different measurement scenarios.
    Returns the parameter section to replace in the TSP script.
    """
    
    scenarios = {
        "voltage_sweep_demo": """
-- Demo: Basic voltage sweep for diode characterization
local sweep_mode = "VOLT"
local four_wire_sensing = false
local terminal_location = "FRONT"
local measure_resistance = false
local nplc = 1.0
local measurement_delay = 0.05
local num_cycles = 1
local start_voltage = 0.0
local stop_voltage = 1.0
local step_voltage = 0.1
local current_limit = 0.01
local start_current = 0.0
local stop_current = 0.01
local step_current = 0.0005
local voltage_limit = 5.0
""",
        
        "resistance_measurement": """
-- High precision resistance measurement with 4-wire sensing
local sweep_mode = "CURR"
local four_wire_sensing = true
local terminal_location = "REAR"
local measure_resistance = true
local nplc = 5.0
local measurement_delay = 0.1
local num_cycles = 3
local start_voltage = 0.0
local stop_voltage = 1.0
local step_voltage = 0.01
local current_limit = 0.01
local start_current = -0.001
local stop_current = 0.001
local step_current = 0.0001
local voltage_limit = 1.0
""",
        
        "fast_characterization": """
-- Fast I-V characterization with multiple cycles
local sweep_mode = "VOLT"
local four_wire_sensing = false
local terminal_location = "FRONT"
local measure_resistance = true
local nplc = 0.1
local measurement_delay = 0.01
local num_cycles = 2
local start_voltage = -1.0
local stop_voltage = 1.0
local step_voltage = 0.05
local current_limit = 0.1
local start_current = 0.0
local stop_current = 0.01
local step_current = 0.0005
local voltage_limit = 5.0
"""
    }
    
    return scenarios.get(sweep_type, scenarios["voltage_sweep_demo"])

def load_and_execute_tsp_script(inst, scenario="voltage_sweep_demo"):
    """Load the TSP script with custom parameters and execute it."""
    
    # Read the base TSP script
    script_path = "/home/runner/work/SMU-2450/SMU-2450/keithley_iv_sweep.tsp"
    
    if not os.path.exists(script_path):
        print(f"Error: TSP script not found at {script_path}")
        return None
    
    with open(script_path, 'r') as f:
        tsp_content = f.read()
    
    # Replace the default parameters with custom ones
    custom_params = customize_tsp_parameters(scenario)
    
    # Find the parameter section and replace it
    # This is a simple approach - in production you might want more sophisticated parsing
    param_start = tsp_content.find("-- Sweep configuration")
    param_end = tsp_content.find("-- ====================================================================", param_start + 1)
    
    if param_start == -1 or param_end == -1:
        print("Warning: Could not find parameter section, using script as-is")
        modified_script = tsp_content
    else:
        modified_script = (tsp_content[:param_start] + 
                          custom_params + 
                          "\n" +
                          tsp_content[param_end:])
    
    print(f"Loading TSP script with '{scenario}' parameters...")
    
    try:
        # Send the script to the instrument
        inst.write("reset()")  # Start with a clean slate
        time.sleep(1)
        
        # For large scripts, we might need to send in chunks
        chunk_size = 1000
        script_lines = modified_script.split('\n')
        
        for i in range(0, len(script_lines), chunk_size):
            chunk = '\n'.join(script_lines[i:i+chunk_size])
            inst.write(chunk)
            time.sleep(0.1)  # Small delay between chunks
        
        print("TSP script loaded successfully")
        
        # Execute the main function
        print("Executing measurement...")
        response = inst.query("main()", delay=1.0)
        
        print("Measurement complete!")
        return response
        
    except Exception as e:
        print(f"Error during script execution: {e}")
        # Try to safely turn off output
        try:
            inst.write("smu.source.output = smu.OFF")
        except:
            pass
        return None

def demonstrate_usage():
    """Demonstrate complete usage of the TSP I-V sweep script."""
    
    print("=" * 60)
    print("Keithley 2450 TSP I-V Sweep Script Demo")
    print("=" * 60)
    
    # Note: This is a demonstration script
    # In a real scenario, you would have an actual instrument connected
    print("Note: This is a demonstration of the script loading process.")
    print("To run with a real instrument, uncomment the connection code below.\n")
    
    # Demonstrate parameter customization
    scenarios = ["voltage_sweep_demo", "resistance_measurement", "fast_characterization"]
    
    for scenario in scenarios:
        print(f"Example parameters for '{scenario}':")
        params = customize_tsp_parameters(scenario)
        print(params)
        print("-" * 40)
    
    # Uncomment below to actually connect to an instrument
    """
    # Find and connect to instrument
    inst = find_keithley_2450()
    if inst is None:
        print("No Keithley 2450 found. Make sure it's connected and drivers are installed.")
        return
    
    try:
        # Run different measurement scenarios
        scenarios_to_run = ["voltage_sweep_demo"]  # Add more as needed
        
        for scenario in scenarios_to_run:
            print(f"\nRunning scenario: {scenario}")
            result = load_and_execute_tsp_script(inst, scenario)
            
            if result:
                print("Script output:")
                print(result)
            else:
                print("Script execution failed")
            
            print("\n" + "="*40)
    
    finally:
        # Always close the connection
        inst.close()
        print("Instrument connection closed")
    """
    
    print("\nTo use this script with a real instrument:")
    print("1. Connect your Keithley 2450 via USB or Ethernet")
    print("2. Install PyVISA and appropriate drivers") 
    print("3. Uncomment the connection code in this script")
    print("4. Modify parameters as needed for your measurement")
    print("5. Run the script")

if __name__ == "__main__":
    demonstrate_usage()
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import pyvisa
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
from time import sleep
import threading
import csv
import datetime

class Keithley2450:
    """
    A class to control the Keithley 2450 SourceMeter using TSP commands.
    This optimized version uses TSP scripting to perform sweeps for maximum efficiency.
    """
    def __init__(self, res_str=None):
        self.rm = pyvisa.ResourceManager()
        self.inst = None
        self.res_str = res_str

    def connect(self):
        if self.inst is not None:
            return
        if self.res_str is None:
            resources = self.rm.list_resources()
            for res in resources:
                if "USB" in res or "TCPIP" in res:
                    self.res_str = res
                    break
        if self.res_str is None:
            raise Exception("No SMU 2450 found.")
        self.inst = self.rm.open_resource(self.res_str)
        self.inst.write_termination = '\n'
        self.inst.read_termination = '\n'
        self.inst.timeout = 20000

    def close(self):
        if self.inst is not None:
            try:
                self.inst.close()
            except pyvisa.errors.VisaIOError:
                pass # Ignore errors if instrument is already disconnected
            self.inst = None

    def idn(self):
        return self.inst.query("*IDN?").strip()

    def write(self, cmd):
        self.inst.write(cmd)

    def query(self, cmd):
        return self.inst.query(cmd).strip()
        
    def output_off(self):
        self.write("smu.source.output = smu.OFF")

    def sweep(self, sweep_mode, start, stop, step, nplc, limit, source_range=None, measure_range=None, sense="2", term="FRON", delay=0.0, show_res=False):
        """
        Performs a sweep by generating and executing a TSP script on the instrument.
        This is much faster than controlling each step from the host computer.
        """
        num_points = int(abs(stop - start) / step) + 1

        # --- Build TSP Script ---
        if sweep_mode == "VOLT":
            source_func, measure_func = "smu.FUNC_DC_VOLTAGE", "smu.FUNC_DC_CURRENT"
            source_limit_cmd = f"smu.source.ilimit.level = {limit}"
            sweep_cmd = f"smu.trigger.source.linear.voltage({start}, {stop}, {num_points})"
            source_range_cmd = f"smu.source.autorangev = smu.OFF\nsmu.source.rangev = {source_range}" if source_range else "smu.source.autorangev = smu.ON"
            measure_range_cmd = f"smu.measure.autorange = smu.OFF\nsmu.measure.range = {measure_range}" if measure_range else "smu.measure.autorange = smu.ON"
        else: # CURR
            source_func, measure_func = "smu.FUNC_DC_CURRENT", "smu.FUNC_DC_VOLTAGE"
            source_limit_cmd = f"smu.source.vlimit.level = {limit}"
            sweep_cmd = f"smu.trigger.source.linear.current({start}, {stop}, {num_points})"
            source_range_cmd = f"smu.source.autorangei = smu.OFF\nsmu.source.rangei = {source_range}" if source_range else "smu.source.autorangei = smu.ON"
            measure_range_cmd = f"smu.measure.autorange = smu.OFF\nsmu.measure.range = {measure_range}" if measure_range else "smu.measure.autorange = smu.ON"

        script = f"""
        reset()
        smu.measure.defbuffer1.clear()
        smu.measure.defbuffer1.capacity = {num_points}
        
        smu.source.func = {source_func}
        smu.measure.func = {measure_func}
        {source_limit_cmd}
        {source_range_cmd}
        {measure_range_cmd}

        smu.measure.nplc = {nplc}
        smu.source.delay = {delay}
        smu.measure.sense = smu.SENSE_{sense}WIRE
        smu.terminals = smu.TERMINALS_{term.upper()}
        
        smu.trigger.count = {num_points}
        {sweep_cmd}
        
        smu.measure.trigmeasure.iv(smu.measure.defbuffer1)
        
        smu.source.output = smu.ON
        smu.trigger.initiate()
        waitcomplete()
        smu.source.output = smu.OFF
        
        printbuffer(1, {num_points}, smu.measure.defbuffer1.sourcevalues, smu.measure.defbuffer1.readings)
        """
        
        # --- Execute Script and Parse Results ---
        self.write(script)
        data_str = self.inst.read()
        
        results = []
        data_points = data_str.strip().split(',')
        if len(data_points) < 2: return []

        for i in range(0, len(data_points), 2):
            try:
                source_val = float(data_points[i])
                reading_val = float(data_points[i+1])
                v_val = source_val if sweep_mode == "VOLT" else reading_val
                i_val = reading_val if sweep_mode == "VOLT" else source_val
                
                resistance = v_val / i_val if (show_res and i_val != 0) else (float('nan') if show_res else None)
                results.append((v_val, i_val, resistance))
            except (ValueError, IndexError):
                continue
        return [results] # Return list of runs for compatibility

# --- GUI Application ---
inst = None
all_runs_data = []
run_colors = ["blue", "red", "green", "orange", "purple", "brown", "black", "cyan", "magenta"]
sweep_abort = [False]

def connect_instrument():
    global inst
    if inst is not None:
        messagebox.showinfo("Already Connected", "Instrument already connected.")
        return
    try:
        inst = Keithley2450()
        inst.connect()
        idn = inst.idn()
        messagebox.showinfo("Connected", f"Instrument ID:\n{idn}")
    except Exception as e:
        messagebox.showerror("Error", f"Connection failed:\n{e}")
        inst = None

def sweep_thread():
    global inst, all_runs_data
    try:
        sweep_mode = sweep_mode_var.get()
        delay = float(delay_entry.get())
        num_cycles = max(1, int(cycles_entry.get()))
        show_res = measure_resistance_var.get()
        nplc = float(nplc_entry.get())
        sense = "4" if four_wire_var.get() else "2"
        term = terminal_select.get()

        if sweep_mode == "VOLT":
            start, stop, step = float(start_voltage_entry.get()), float(stop_voltage_entry.get()), float(step_voltage_entry.get())
            limit = float(current_limit_entry.get())
            source_range = float(s_range_str) if (s_range_str := voltage_source_range_entry.get()) else None
            measure_range = float(m_range_str) if (m_range_str := voltage_measure_range_entry.get()) else None
        else: # CURR
            start, stop, step = float(start_current_entry.get()), float(stop_current_entry.get()), float(step_current_entry.get())
            limit = float(voltage_limit_entry.get())
            source_range = float(s_range_str) if (s_range_str := current_source_range_entry.get()) else None
            measure_range = float(m_range_str) if (m_range_str := current_measure_range_entry.get()) else None

        all_runs_data.clear()
        ax.clear()
        canvas.draw()
        
        progress_bar["maximum"] = num_cycles
        for cycle in range(num_cycles):
            if sweep_abort[0]: break
            progress_label.config(text=f"Running Cycle {cycle + 1}/{num_cycles}")
            
            # This single call runs the entire sweep on the instrument
            run_result = inst.sweep(
                sweep_mode, start, stop, step, nplc, limit,
                source_range, measure_range, sense, term, delay, show_res
            )
            if run_result:
                all_runs_data.extend(run_result)

            # Update plot after each full cycle
            ax.clear()
            for i, run_data in enumerate(all_runs_data):
                v_data = [d[0] for d in run_data]
                i_data = [d[1] for d in run_data]
                ax.plot(v_data if sweep_mode == "VOLT" else i_data, 
                        i_data if sweep_mode == "VOLT" else v_data, 
                        marker='o', linestyle='-', color=run_colors[i % len(run_colors)], label=f"Run {i+1}")
            
            ax.set_title("I-V Sweep" if sweep_mode == "VOLT" else "V-I Sweep")
            ax.set_xlabel("Voltage (V)" if sweep_mode == "VOLT" else "Current (A)")
            ax.set_ylabel("Current (A)" if sweep_mode == "VOLT" else "Voltage (V)")
            ax.legend()
            ax.grid(True)
            canvas.draw()
            progress_bar["value"] = cycle + 1
            root.update_idletasks()

        progress_label.config(text="Sweep Complete" if not sweep_abort[0] else "Sweep Aborted")
        if not sweep_abort[0]:
            messagebox.showinfo("Sweep Complete", "Sweep completed successfully.")
        else:
            messagebox.showinfo("Sweep Aborted", "Sweep aborted by user.")
        sweep_abort[0] = False

    except Exception as e:
        if not sweep_abort[0]: messagebox.showerror("Error", f"Sweep failed:\n{e}")

def start_sweep():
    if inst is None:
        messagebox.showerror("Error", "Instrument not connected.")
        return
    sweep_abort[0] = False
    thread = threading.Thread(target=sweep_thread, daemon=True)
    thread.start()

def suggest_filename():
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"iv_sweep_{now}"

def save_data_and_graph():
    if not all_runs_data:
        messagebox.showwarning("No Data", "No data to save. Please run a sweep first.")
        return

    default_filename = suggest_filename()
    filename_csv = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile=default_filename + ".csv")
    if not filename_csv: return

    show_res = measure_resistance_var.get()
    header = []
    for i in range(len(all_runs_data)):
        header.extend([f"Run{i+1}_Voltage(V)", f"Run{i+1}_Current(A)"])
        if show_res: header.append(f"Run{i+1}_Resistance(Ohm)")

    max_len = max(len(run) for run in all_runs_data) if all_runs_data else 0
    with open(filename_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for r in range(max_len):
            row = []
            for run_data in all_runs_data:
                if r < len(run_data):
                    v, i, res = run_data[r]
                    row.extend([v, i])
                    if show_res: row.append(res)
                else:
                    row.extend(["", ""] + ([""] if show_res else []))
            writer.writerow(row)
    messagebox.showinfo("Saved", f"Data saved to:\n{filename_csv}")

def abort_sweep():
    sweep_abort[0] = True

def on_closing():
    global inst
    if inst is not None:
        try:
            inst.output_off()
            inst.close()
        except Exception: pass
    root.destroy()

# --- GUI Setup ---
root = tk.Tk()
root.title(f"Keithley 2450 Sweep GUI (Optimized) by @{__user_login__}")
root.protocol("WM_DELETE_WINDOW", on_closing)

# --- Main Frames ---
left_panel = tk.Frame(root, padx=10, pady=10)
left_panel.pack(side=tk.LEFT, fill=tk.Y, anchor="n")
center_panel = tk.Frame(root, padx=10, pady=10)
center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
right_panel = tk.Frame(root, padx=10, pady=10)
right_panel.pack(side=tk.LEFT, fill=tk.Y, anchor="n")

# --- Left Panel ---
tk.Label(left_panel, text="Sweep Mode:", font="-weight bold").pack(anchor='w')
sweep_mode_var = tk.StringVar(value="VOLT")
tk.Radiobutton(left_panel, text="Voltage Source", variable=sweep_mode_var, value="VOLT").pack(anchor='w')
tk.Radiobutton(left_panel, text="Current Source", variable=sweep_mode_var, value="CURR").pack(anchor='w')

voltage_frame = tk.LabelFrame(left_panel, text="Voltage Sweep Parameters", padx=5, pady=5)
current_frame = tk.LabelFrame(left_panel, text="Current Sweep Parameters", padx=5, pady=5)

def update_entries(*args):
    if sweep_mode_var.get() == "VOLT":
        voltage_frame.pack(pady=10, fill="x", anchor='n')
        current_frame.pack_forget()
    else:
        current_frame.pack(pady=10, fill="x", anchor='n')
        voltage_frame.pack_forget()
sweep_mode_var.trace("w", update_entries)

# --- Voltage Frame Widgets ---
tk.Label(voltage_frame, text="Start (V):").grid(row=0, column=0, sticky='w', pady=2)
start_voltage_entry = tk.Entry(voltage_frame, width=15); start_voltage_entry.insert(0, "0"); start_voltage_entry.grid(row=0, column=1, pady=2)
tk.Label(voltage_frame, text="Stop (V):").grid(row=1, column=0, sticky='w', pady=2)
stop_voltage_entry = tk.Entry(voltage_frame, width=15); stop_voltage_entry.insert(0, "1"); stop_voltage_entry.grid(row=1, column=1, pady=2)
tk.Label(voltage_frame, text="Step (V):").grid(row=2, column=0, sticky='w', pady=2)
step_voltage_entry = tk.Entry(voltage_frame, width=15); step_voltage_entry.insert(0, "0.1"); step_voltage_entry.grid(row=2, column=1, pady=2)
tk.Label(voltage_frame, text="I Limit (A):").grid(row=3, column=0, sticky='w', pady=2)
current_limit_entry = tk.Entry(voltage_frame, width=15); current_limit_entry.insert(0, "0.01"); current_limit_entry.grid(row=3, column=1, pady=2)
tk.Label(voltage_frame, text="Source Range (V):").grid(row=4, column=0, sticky='w', pady=2)
voltage_source_range_entry = tk.Entry(voltage_frame, width=15); voltage_source_range_entry.grid(row=4, column=1, pady=2)
tk.Label(voltage_frame, text="Measure Range (A):").grid(row=5, column=0, sticky='w', pady=2)
voltage_measure_range_entry = tk.Entry(voltage_frame, width=15); voltage_measure_range_entry.grid(row=5, column=1, pady=2)

# --- Current Frame Widgets ---
tk.Label(current_frame, text="Start (A):").grid(row=0, column=0, sticky='w', pady=2)
start_current_entry = tk.Entry(current_frame, width=15); start_current_entry.insert(0, "0"); start_current_entry.grid(row=0, column=1, pady=2)
tk.Label(current_frame, text="Stop (A):").grid(row=1, column=0, sticky='w', pady=2)
stop_current_entry = tk.Entry(current_frame, width=15); stop_current_entry.insert(0, "0.01"); stop_current_entry.grid(row=1, column=1, pady=2)
tk.Label(current_frame, text="Step (A):").grid(row=2, column=0, sticky='w', pady=2)
step_current_entry = tk.Entry(current_frame, width=15); step_current_entry.insert(0, "0.001"); step_current_entry.grid(row=2, column=1, pady=2)
tk.Label(current_frame, text="V Limit (V):").grid(row=3, column=0, sticky='w', pady=2)
voltage_limit_entry = tk.Entry(current_frame, width=15); voltage_limit_entry.insert(0, "10"); voltage_limit_entry.grid(row=3, column=1, pady=2)
tk.Label(current_frame, text="Source Range (A):").grid(row=4, column=0, sticky='w', pady=2)
current_source_range_entry = tk.Entry(current_frame, width=15); current_source_range_entry.grid(row=4, column=1, pady=2)
tk.Label(current_frame, text="Measure Range (V):").grid(row=5, column=0, sticky='w', pady=2)
current_measure_range_entry = tk.Entry(current_frame, width=15); current_measure_range_entry.grid(row=5, column=1, pady=2)

# --- Common Settings ---
common_settings_frame = tk.LabelFrame(left_panel, text="Common Settings", padx=5, pady=5)
common_settings_frame.pack(fill="x", pady=10)
four_wire_var = tk.BooleanVar()
tk.Checkbutton(common_settings_frame, text="4-Wire Sense", variable=four_wire_var).pack(anchor='w')
measure_resistance_var = tk.BooleanVar()
tk.Checkbutton(common_settings_frame, text="Calculate Resistance", variable=measure_resistance_var).pack(anchor='w')
tk.Label(common_settings_frame, text="NPLC:").pack(anchor='w', pady=(5,0))
nplc_entry = tk.Entry(common_settings_frame); nplc_entry.insert(0, "1"); nplc_entry.pack(fill='x')
tk.Label(common_settings_frame, text="Delay (s):").pack(anchor='w', pady=(5,0))
delay_entry = tk.Entry(common_settings_frame); delay_entry.insert(0, "0.05"); delay_entry.pack(fill='x')
tk.Label(common_settings_frame, text="Cycles:").pack(anchor='w', pady=(5,0))
cycles_entry = tk.Entry(common_settings_frame); cycles_entry.insert(0, "1"); cycles_entry.pack(fill='x')
tk.Label(common_settings_frame, text="Terminals:").pack(anchor='w', pady=(5,0))
terminal_select = tk.StringVar(value="FRON")
tk.Radiobutton(common_settings_frame, text="Front", variable=terminal_select, value="FRON").pack(anchor='w')
tk.Radiobutton(common_settings_frame, text="Rear", variable=terminal_select, value="REAR").pack(anchor='w')

# --- Center Panel (Graph) ---
fig, ax = plt.subplots()
canvas = FigureCanvasTkAgg(fig, master=center_panel)
canvas.draw()
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
toolbar = NavigationToolbar2Tk(canvas, center_panel)
toolbar.update()

# --- Right Panel (Controls) ---
tk.Button(right_panel, text="Connect", command=connect_instrument).pack(pady=5, fill='x')
tk.Button(right_panel, text="Start Sweep", command=start_sweep, bg="#4CAF50", fg="white").pack(pady=5, fill='x')
tk.Button(right_panel, text="Abort Sweep", command=abort_sweep, bg="#F44336", fg="white").pack(pady=5, fill='x')
tk.Button(right_panel, text="Save Data", command=save_data_and_graph).pack(pady=5, fill='x')
progress_label = tk.Label(right_panel, text="Progress: 0%")
progress_label.pack(pady=5)
progress_bar = ttk.Progressbar(right_panel, orient='horizontal', mode='determinate')
progress_bar.pack(pady=5, fill='x')

update_entries()
root.mainloop()
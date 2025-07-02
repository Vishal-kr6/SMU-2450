import tkinter as tk
from tkinter import messagebox, filedialog
import pyvisa
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import threading
import time
import csv

inst = None
all_runs_data = []
run_colors = ["blue", "red", "green", "orange", "purple", "brown", "black", "cyan", "magenta"]

def connect_instrument():
    global inst
    if inst is not None:
        messagebox.showinfo("Already Connected", "Instrument already connected.")
        return
    try:
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        found = False
        for res in resources:
            if "USB" in res or "TCPIP" in res:
                inst = rm.open_resource(res)
                idn = inst.query("*IDN?")
                messagebox.showinfo("Connected", f"Instrument ID:\n{idn}")
                found = True
                break
        if not found:
            messagebox.showwarning("Not Found", "No USB or TCPIP SMU found.")
    except Exception as e:
        messagebox.showerror("Error", f"Connection failed:\n{e}")

def build_tsp_script(sweep_mode, start, stop, step, limit, delay, nplc, cycles, terminal, sense_mode, show_res):
    """
    Build a simple, robust TSP script for DC sweep using a manual for loop (no sweeplinear, no trigger model).
    Supports both voltage and current sweep modes.
    """
    if step == 0:
        raise ValueError("Step cannot be zero.")
    terminal_const = "smu.TERMINALS_FRONT" if terminal == "FRON" else "smu.TERMINALS_REAR"
    sense_const = "smu.SENSE_4WIRE" if sense_mode == "4" else "smu.SENSE_2WIRE"
    if sweep_mode == "VOLT":
        src_func = "smu.FUNC_DC_VOLTAGE"
        meas_func = "smu.FUNC_DC_CURRENT"
        limit_str = f"smu.source.ilimit.level = {limit}"
        sweep_var = "v"
        level_assignment = "smu.source.level = v"
        start_val = start
        stop_val = stop
        step_val = step
    else:
        src_func = "smu.FUNC_DC_CURRENT"
        meas_func = "smu.FUNC_DC_VOLTAGE"
        limit_str = f"smu.source.vlimit.level = {limit}"
        sweep_var = "i"
        level_assignment = "smu.source.level = i"
        start_val = start
        stop_val = stop
        step_val = step
    tsp_script = f'''
reset()
smu.terminals = {terminal_const}
smu.source.func = {src_func}
smu.measure.func = {meas_func}
{limit_str}
smu.source.autorange = smu.ON
smu.measure.autorange = smu.ON
smu.measure.nplc = {nplc}
smu.measure.sense = {sense_const}
defbuffer1.clear()
defbuffer1.collecttimestamps = 1
smu.source.output = smu.ON
for {sweep_var} = {start_val}, {stop_val}, {step_val} do
    {level_assignment}
    delay({delay})
    smu.measure.read(defbuffer1)
end
smu.source.output = smu.OFF
printbuffer(1, defbuffer1.n, defbuffer1.sourcevalues, defbuffer1.readings)
'''
    return '\n'.join([line.strip() for line in tsp_script.strip().splitlines()])

def parse_tsp_output(output):
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    values = []
    for line in reversed(lines):
        try:
            candidate = [float(v.strip()) for v in line.split(',') if v.strip()]
            if len(candidate) >= 2 and len(candidate) % 2 == 0:
                values = candidate
                break
        except ValueError:
            continue
    data = []
    for v, i in zip(values[0::2], values[1::2]):
        r = v / i if i != 0 else None
        data.append((v, i, r))
    return data

def sweep_thread():
    global inst, all_runs_data
    try:
        sweep_mode = sweep_mode_var.get()
        sense_mode_value = sensing_mode.get()
        terminal = terminal_select.get()
        show_res = measure_resistance_var.get()
        delay = float(delay_entry.get())
        nplc = float(nplc_entry.get())
        cycles = int(cycles_entry.get())
        if sweep_mode == "VOLT":
            start = float(start_voltage_entry.get())
            stop = float(stop_voltage_entry.get())
            step = float(step_voltage_entry.get())
            limit = float(current_limit_entry.get())
        else:
            start = float(start_current_entry.get())
            stop = float(stop_current_entry.get())
            step = float(step_current_entry.get())
            limit = float(voltage_limit_entry.get())
        tsp_code = build_tsp_script(
            sweep_mode, start, stop, step, limit, delay, nplc, cycles, terminal, sense_mode_value, show_res
        )
        # Send the entire TSP script at once!
        tsp_output = inst.query(tsp_code)
        data = parse_tsp_output(tsp_output)
        if not data:
            messagebox.showerror("No Data", "No sweep data read from instrument.")
            return
        all_runs_data.clear()
        all_runs_data.append(data)
        plot_data()
        messagebox.showinfo("Sweep Complete", "Sweep completed and data received.")
    except Exception as e:
        messagebox.showerror("Error", f"Sweep failed:\n{e}")

def plot_data():
    ax.clear()
    sweep_mode = sweep_mode_var.get()
    show_res = measure_resistance_var.get()
    for idx, run_data in enumerate(all_runs_data):
        v = [d[0] for d in run_data]
        i = [d[1] for d in run_data]
        color = run_colors[idx % len(run_colors)]
        label = f"Run {idx+1}"
        if sweep_mode == "VOLT":
            ax.plot(v, i, marker='o', color=color, label=label)
            ax.set_xlabel("Voltage (V)")
            ax.set_ylabel("Current (A)")
            ax.set_title("I-V Sweep (Voltage Source, Current Measure)")
        else:
            ax.plot(i, v, marker='o', color=color, label=label)
            ax.set_xlabel("Current (A)")
            ax.set_ylabel("Voltage (V)")
            ax.set_title("V-I Sweep (Current Source, Voltage Measure)")
        if show_res:
            ax2 = ax.twinx()
            r = [d[2] for d in run_data]
            if sweep_mode == "VOLT":
                ax2.plot(v, r, marker='x', color="gray", alpha=0.3, label="Resistance (Ohm)")
                ax2.set_ylabel("Resistance (Ohm)")
            else:
                ax2.plot(i, r, marker='x', color="gray", alpha=0.3, label="Resistance (Ohm)")
                ax2.set_ylabel("Resistance (Ohm)")
    ax.legend()
    ax.figure.tight_layout()
    canvas.draw()

def start_sweep():
    thread = threading.Thread(target=sweep_thread)
    thread.daemon = True
    thread.start()

def save_data_and_graph():
    if not all_runs_data or len(all_runs_data) == 0:
        messagebox.showwarning("No Data", "No data to save. Please run a sweep first.")
        return
    sweep_mode = sweep_mode_var.get()
    show_res = measure_resistance_var.get()
    now = time.strftime("%Y%m%d_%H%M%S")
    if sweep_mode == "VOLT":
        default_filename = f"iv_sweep_voltage_{now}"
    else:
        default_filename = f"iv_sweep_current_{now}"
    filetypes_img = [("PNG image", "*.png")]
    filename_img = filedialog.asksaveasfilename(
        defaultextension=".png", filetypes=filetypes_img, initialfile=default_filename + ".png"
    )
    if filename_img:
        fig2, ax2 = plt.subplots(figsize=(8, 6))
        for idx, run_data in enumerate(all_runs_data):
            v = [d[0] for d in run_data]
            i = [d[1] for d in run_data]
            color = run_colors[idx % len(run_colors)]
            label = f"Run {idx + 1}"
            if sweep_mode == "VOLT":
                ax2.plot(v, i, marker='o', color=color, label=label)
                ax2.set_xlabel("Voltage (V)")
                ax2.set_ylabel("Current (A)")
                ax2.set_title("I-V Sweep (Voltage Source, Current Measure)")
            else:
                ax2.plot(i, v, marker='o', color=color, label=label)
                ax2.set_xlabel("Current (A)")
                ax2.set_ylabel("Voltage (V)")
                ax2.set_title("V-I Sweep (Current Source, Voltage Measure)")
        ax2.legend()
        fig2.tight_layout()
        fig2.savefig(filename_img)
        plt.close(fig2)
    filetypes_csv = [("CSV files", "*.csv")]
    filename_csv = filedialog.asksaveasfilename(
        defaultextension=".csv", filetypes=filetypes_csv, initialfile=default_filename + ".csv"
    )
    if filename_csv:
        max_points = max(len(run) for run in all_runs_data)
        col_header = []
        for idx in range(len(all_runs_data)):
            base = f"run{idx+1}"
            col_header.extend([f"{base}_V", f"{base}_I"])
            if show_res:
                col_header.append(f"{base}_R")
        with open(filename_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(col_header)
            for row_idx in range(max_points):
                row = []
                for run in all_runs_data:
                    if row_idx < len(run):
                        v, i, r = run[row_idx]
                        row.append(v)
                        row.append(i)
                        if show_res:
                            row.append(r)
                    else:
                        row.extend(["", ""] + ([""] if show_res else []))
                writer.writerow(row)
        messagebox.showinfo("Saved", f"Data and graph saved to:\n{filename_csv} and\n{filename_img}")

def abort_sweep():
    if inst:
        try:
            inst.write("exit()")
        except Exception:
            pass

def reset_view():
    ax.clear()
    ax.set_xlabel("")
    ax.set_ylabel("")
    canvas.draw()

def scroll_zoom(event):
    base_scale = 1.1
    x, y = event.x, event.y
    inv = ax.transData.inverted()
    xdata, ydata = inv.transform((x, y))
    scale_factor = 1 / base_scale if event.delta > 0 else base_scale
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    new_xlim = [xdata - (xdata - xlim[0]) * scale_factor,
                xdata + (xlim[1] - xdata) * scale_factor]
    new_ylim = [ydata - (ydata - ylim[0]) * scale_factor,
                ydata + (ylim[1] - ydata) * scale_factor]
    ax.set_xlim(new_xlim)
    ax.set_ylim(new_ylim)
    canvas.draw()

def on_closing():
    global inst
    if inst is not None:
        try:
            inst.close()
        except Exception:
            pass
    root.destroy()

root = tk.Tk()
root.title("Keithley 2450 Multi-Run I-V Sweep GUI (TSP Fast, Plot, Save, 2/4-Wire, Front/Rear)")
root.geometry("1260x880")
root.protocol("WM_DELETE_WINDOW", on_closing)

# LEFT PANEL
left_panel = tk.Frame(root)
left_panel.pack(side=tk.LEFT, padx=10, pady=10, anchor="n")

tk.Label(left_panel, text="Sweep Mode:").pack()
sweep_mode_var = tk.StringVar(value="VOLT")
def update_param_fields():
    if sweep_mode_var.get() == "VOLT":
        voltage_frame.pack(pady=(10, 0), fill="x")
        current_frame.pack_forget()
    else:
        current_frame.pack(pady=(10, 0), fill="x")
        voltage_frame.pack_forget()
sweep_mode_var.trace('w', lambda *args: update_param_fields())
tk.Radiobutton(left_panel, text="Voltage Source, Current Measure", variable=sweep_mode_var, value="VOLT").pack()
tk.Radiobutton(left_panel, text="Current Source, Voltage Measure", variable=sweep_mode_var, value="CURR").pack()

measure_resistance_var = tk.BooleanVar()
tk.Checkbutton(left_panel, text="Measure Resistance (Ohm) by V/I", variable=measure_resistance_var).pack()

nplc_frame = tk.Frame(left_panel)
nplc_frame.pack(fill="x")
tk.Label(nplc_frame, text="NPLC:").pack(side=tk.LEFT)
nplc_entry = tk.Entry(nplc_frame, width=5)
nplc_entry.insert(0, "1")
nplc_entry.pack(side=tk.LEFT, padx=(5, 0))
tk.Label(nplc_frame, text="(Integration Time)").pack(side=tk.LEFT, padx=(5, 0))

delay_frame = tk.Frame(left_panel)
delay_frame.pack(fill="x")
tk.Label(delay_frame, text="Measurement Delay (s):").pack(side=tk.LEFT)
delay_entry = tk.Entry(delay_frame, width=5)
delay_entry.insert(0, "0.05")
delay_entry.pack(side=tk.LEFT, padx=(5, 0))

cycles_frame = tk.Frame(left_panel)
cycles_frame.pack(fill="x")
tk.Label(cycles_frame, text="No. of Cycles:").pack(side=tk.LEFT)
cycles_entry = tk.Entry(cycles_frame, width=5)
cycles_entry.insert(0, "1")
cycles_entry.pack(side=tk.LEFT, padx=(5, 0))

voltage_frame = tk.LabelFrame(left_panel, text="Voltage Sweep Parameters")
voltage_frame.pack(pady=(10, 0), fill="x")
tk.Label(voltage_frame, text="Start Voltage (V):").pack()
start_voltage_entry = tk.Entry(voltage_frame)
start_voltage_entry.insert(0, "0")
start_voltage_entry.pack()
tk.Label(voltage_frame, text="Stop Voltage (V):").pack()
stop_voltage_entry = tk.Entry(voltage_frame)
stop_voltage_entry.insert(0, "1")
stop_voltage_entry.pack()
tk.Label(voltage_frame, text="Step Voltage (V):").pack()
step_voltage_entry = tk.Entry(voltage_frame)
step_voltage_entry.insert(0, "0.01")
step_voltage_entry.pack()
tk.Label(voltage_frame, text="Current Limit (A):").pack(pady=(10, 0))
current_limit_entry = tk.Entry(voltage_frame)
current_limit_entry.insert(0, "0.01")
current_limit_entry.pack()

current_frame = tk.LabelFrame(left_panel, text="Current Sweep Parameters")
current_frame.pack(pady=(10, 0), fill="x")
tk.Label(current_frame, text="Start Current (A):").pack()
start_current_entry = tk.Entry(current_frame)
start_current_entry.insert(0, "0")
start_current_entry.pack()
tk.Label(current_frame, text="Stop Current (A):").pack()
stop_current_entry = tk.Entry(current_frame)
stop_current_entry.insert(0, "0.01")
stop_current_entry.pack()
tk.Label(current_frame, text="Step Current (A):").pack()
step_current_entry = tk.Entry(current_frame)
step_current_entry.insert(0, "0.0005")
step_current_entry.pack()
tk.Label(current_frame, text="Voltage Limit (V):").pack(pady=(10, 0))
voltage_limit_entry = tk.Entry(current_frame)
voltage_limit_entry.insert(0, "5")
voltage_limit_entry.pack()

def update_limit_fields(*args):
    if sweep_mode_var.get() == "VOLT":
        current_limit_entry.config(state="normal")
        voltage_limit_entry.config(state="disabled")
    else:
        current_limit_entry.config(state="disabled")
        voltage_limit_entry.config(state="normal")
sweep_mode_var.trace('w', update_limit_fields)
update_limit_fields()

# --- Sensing and Terminal moved to right panel bottom ---
center_panel = tk.Frame(root)
center_panel.pack(side=tk.LEFT, padx=10, pady=10, anchor="n")
fig, ax = plt.subplots(figsize=(7, 5))
canvas = FigureCanvasTkAgg(fig, master=center_panel)
canvas.draw()
canvas.get_tk_widget().pack()
toolbar = NavigationToolbar2Tk(canvas, center_panel)
toolbar.update()

right_panel = tk.Frame(root)
right_panel.pack(side=tk.LEFT, padx=10, pady=10, anchor="n")
tk.Button(right_panel, text="Connect to Keithley", command=connect_instrument).pack(pady=5)
tk.Button(right_panel, text="Start Sweep", command=start_sweep).pack(pady=5)
tk.Button(right_panel, text="Abort Sweep", command=abort_sweep).pack(pady=5)
tk.Button(right_panel, text="Save Data & Graphs", command=save_data_and_graph).pack(pady=5)
tk.Button(right_panel, text="Reset View", command=reset_view).pack(pady=5)

# Add Sensing/Terminal group at bottom of right panel
sensing_terminal_frame = tk.Frame(right_panel)
sensing_terminal_frame.pack(pady=(30, 0), side=tk.BOTTOM, anchor="s")

tk.Label(sensing_terminal_frame, text="Sensing Mode:").pack()
sensing_mode = tk.StringVar(value="2")
tk.Radiobutton(sensing_terminal_frame, text="2-Wire", variable=sensing_mode, value="2").pack(anchor="w")
tk.Radiobutton(sensing_terminal_frame, text="4-Wire", variable=sensing_mode, value="4").pack(anchor="w")

tk.Label(sensing_terminal_frame, text="Terminal Location:").pack(pady=(10, 0))
terminal_select = tk.StringVar(value="FRON")
tk.Radiobutton(sensing_terminal_frame, text="Front", variable=terminal_select, value="FRON").pack(anchor="w")
tk.Radiobutton(sensing_terminal_frame, text="Rear", variable=terminal_select, value="REAR").pack(anchor="w")

canvas.get_tk_widget().bind("<MouseWheel>", scroll_zoom)

root.mainloop()
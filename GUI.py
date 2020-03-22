import datetime
import os
import struct
import sys
import time
import numpy as np
from tkinter import *

import matplotlib.animation as animation
import matplotlib.style
import serial
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import visa
import queue as Queue
import threading

import statistics

if sys.version_info[0] < 3:
    import Tkinter as tk
else:
    import tkinter as tk

matplotlib.style.use('ggplot')

# SMU_ID = 'USB0::0x0957::0x8B18::MY51141538::0::INSTR'
SMU_ID = 'USB0::0x0957::0x8E18::MY51142866::0::INSTR'
DEFAULT_INPUT_RES = "0.0"

MAX_INPUT_CURRENT = 0.1
OUTPUT_VOLTAGE = 4.05
MAX_OUTPUT_CURRENT = 0.001
DEFAULT_INPUT_VOLTAGE = 0.050

TRANSITION_TIME_SEC = 900 # 900s =  15 min
# TRANSITION_TIME_SEC = 180 # 180s =  3 min

class SmuThreadedTask(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue

        # Set up smu
        self.rm = visa.ResourceManager()
        self.smu = self.rm.open_resource(SMU_ID)

        self.smu_output_volt = 0
        self.smu_output_curr = 0
        self.smu_input_volt = 0
        self.smu_input_curr = 0

        self.smu_input_target_volt = DEFAULT_INPUT_VOLTAGE
        self.change_input_volt_flag = False;

        self.pause = True
        self.setup_smu()


    def setup_smu(self):
        # Full setup
        print("SMU setup...")

        print("Reset smu: ", self.smu.write("*RST"))
        print("Clear status byte reg: ", self.smu.write("*CLS"))


        print("Set source 1 output shape: ", self.smu.write("SOUR1:FUNC DC"))
        print("Get source 1 output shape: ", self.smu.query("SOUR1:FUNC?"))
        print("Set source 2 output shape: ", self.smu.write("SOUR2:FUNC DC"))
        print("Get source 2 output shape: ", self.smu.query("SOUR2:FUNC?"))

        print("Set source 1 output mode: ", self.smu.write("SOUR1:FUNC:MODE VOLT"))
        print("Get source 1 output mode: ", self.smu.query("SOUR1:FUNC:MODE?"))
        print("Set source 2 output mode: ", self.smu.write("SOUR2:FUNC:MODE VOLT"))
        print("Get source 2 output mode: ", self.smu.query("SOUR2:FUNC:MODE?"))

        print("Set voltage 1 range: ", self.smu.write("SOUR1:VOLT:RANG 20"))
        print("Get voltage 1 range: ", self.smu.query("SOUR1:VOLT:RANG?"))
        print("Set voltage 2 range: ", self.smu.write("SOUR2:VOLT:RANGE 0.2"))
        print("Get voltage 2 range: ", self.smu.query("SOUR2:VOLT:RANG?"))

        print("Set current 1 range: ", self.smu.write("SENS1:CURR:RANGE 0.001"))
        print("Get current 1 range: ", self.smu.query("SENS1:CURR:RANGE?"))
        print("Set current 2 range: ", self.smu.write("SENS2:CURR:RANGE 0.1"))
        print("Get current 2 range: ", self.smu.query("SENS2:CURR:RANGE?"))

        print("Set current 1 limit: ", self.smu.write("SENS1:CURR:PROT " + str(MAX_OUTPUT_CURRENT)))
        print("Get current 1 limit: ", self.smu.query("SENS1:CURR:PROT?"))
        print("Set current 2 limit: ", self.smu.write("SENS2:CURR:PROT " + str(MAX_INPUT_CURRENT)))
        print("Get current 2 limit: ", self.smu.query("SENS2:CURR:PROT?"))

        print("Set integration time V 1: ", self.smu.write("SENS1:VOLT:APER 0.5"))
        print("Get integration time V 1: ", self.smu.query("SENS1:VOLT:APER?"))
        print("Set integration time V 2: ", self.smu.write("SENS2:VOLT:APER 0.5"))
        print("Get integration time V 2: ", self.smu.query("SENS2:VOLT:APER?"))

        print("Set integration time I 1: ", self.smu.write("SENS1:CURR:APER 0.5"))
        print("Get integration time I 1: ", self.smu.query("SENS1:CURR:APER?"))
        print("Set integration time I 2: ", self.smu.write("SENS2:CURR:APER 0.5"))
        print("Get integration time I 2: ", self.smu.query("SENS2:CURR:APER?"))

        print("Source voltage...")

        print("Set sourced voltage 1: ", self.smu.write("SOUR1:VOLT 4.05"))
        # print("Set sourced voltage: ", self.smu.write("SOUR1:VOLT 3.7"))
        print("Get sourced voltage 1: ", self.smu.query("SOUR1:VOLT?"))
        print("Set sourced voltage 2: ", self.smu.write("SOUR2:VOLT " + str(self.smu_input_target_volt)))
        print("Get sourced voltage 2: ", self.smu.query("SOUR2:VOLT?"))

        print("Enable outputs...")
        print("Set output 1 on: ", self.smu.write("OUTPUT1 ON"))
        print("Is output 1 on?: ", self.smu.query("OUTPUT1?"))
        print("Set output 2 on: ", self.smu.write("OUTPUT2 ON"))
        print("Is output 2 on?: ", self.smu.query("OUTPUT2?"))

    def pause_smu(self):
        self.pause = True

    def resume_smu(self):
        self.pause = False

    def smu_measure(self):
        self.smu_input_volt = float(self.smu.query("MEAS:VOLT? (@2)")[:-1])
        self.smu_input_curr = float(self.smu.query("MEAS:CURR? (@2)")[:-1])
        self.smu_output_volt = float(self.smu.query("MEAS:VOLT? (@1)")[:-1])
        self.smu_output_curr = float(self.smu.query("MEAS:CURR? (@1)")[:-1])

    def smu_set_new_input_voltage(self, input_voltage):
        if (input_voltage < 0) or (input_voltage > 0.2):
            print("Error: input voltage ", input_voltage, " is out of allowed range")
        else:
            self.smu_input_target_volt = input_voltage
            self.change_input_volt_flag = True;


    def smu_change_input_voltage(self):
        if (self.smu_input_target_volt < 0) or (self.smu_input_target_volt > 0.2):
            print("Error: input voltage ", input_voltage, " is out of allowed range")
        else:
            print("Disable output 2...")
            print("Set output 2 off: ", self.smu.write("OUTPUT2 OFF"))
            print("Is output 2 on?: ", self.smu.query("OUTPUT2?")) 

            print("Set sourced voltage 2 to ", str(self.smu_input_target_volt), " : ", 
                  self.smu.write("SOUR2:VOLT " + str(self.smu_input_target_volt)))
            print("Get sourced voltage 2: ", self.smu.query("SOUR2:VOLT?"))

            print("Enable output 2...")
            print("Set output 2 onn: ", self.smu.write("OUTPUT2 ON"))
            print("Is output 2 on?: ", self.smu.query("OUTPUT2?")) 

            # Clear the flag
            self.change_input_volt_flag = False;


    def close_smu(self):
        self.smu.close()
        print("SMU closed.")

    def run(self):
        while True:
            if self.pause is False:

                # Check the input voltage
                if self.change_input_volt_flag is True:
                    self.smu_change_input_voltage()
                # Measure I and V
                self.smu_measure()
                # Put data in a queue
                self.queue.put([self.smu_input_volt, self.smu_input_curr, self.smu_output_volt, self.smu_output_curr])
            else:
                time.sleep(0.1)


class App:
    def __init__(self, master):
        self.master = master

        # File name for data and final data
        self.data_file_name = 'data_' + datetime.datetime.now().strftime('%d_%m_%Y_%H_%M') + '.txt'

        # Align rows and columns of master
        Grid.rowconfigure(master, 0, weight=1)
        Grid.rowconfigure(master, 1, weight=1)
        Grid.columnconfigure(master, 0, weight=1)
        Grid.columnconfigure(master, 1, weight=1)
        Grid.columnconfigure(master, 2, weight=1)
        Grid.columnconfigure(master, 3, weight=1)
        Grid.columnconfigure(master, 4, weight=1)
        Grid.columnconfigure(master, 5, weight=1)
        Grid.columnconfigure(master, 6, weight=1)

        # Create bottom frame for buttons, labels and entry windows
        self.bottom_frame = Frame(self.master, background="white")
        self.bottom_frame.grid(row=1, column=0, columnspan=6, sticky=N + S + E + W)

        # Configure sub grid
        Grid.columnconfigure(self.bottom_frame, 0, weight=1)
        Grid.columnconfigure(self.bottom_frame, 1, weight=1)
        Grid.columnconfigure(self.bottom_frame, 2, weight=1)
        Grid.columnconfigure(self.bottom_frame, 3, weight=1)
        Grid.columnconfigure(self.bottom_frame, 4, weight=1)
        Grid.columnconfigure(self.bottom_frame, 5, weight=1)
        Grid.rowconfigure(self.bottom_frame, 0, weight=1)
        Grid.rowconfigure(self.bottom_frame, 1, weight=1)
        Grid.rowconfigure(self.bottom_frame, 2, weight=1)
        Grid.rowconfigure(self.bottom_frame, 3, weight=1)

        # Create labels (names)
        label_1 = Label(self.bottom_frame, text="Input Voltage, mV", fg="black", bg="white")
        label_2 = Label(self.bottom_frame, text="Input Current, mA", fg="black", bg="white")
        label_3 = Label(self.bottom_frame, text="Input resistance, Ohm", fg="black", bg="white")
        label_4 = Label(self.bottom_frame, text="Output Voltage, V", fg="black", bg="white")
        label_5 = Label(self.bottom_frame, text="Output Current, mA", fg="black", bg="white")
        # label_6 = Label(self.bottom_frame, text="COM port", fg="black", bg="white")
        label_7 = Label(self.bottom_frame, text="Set Output Voltage, mV", fg="black", bg="white")
        label_8 = Label(self.bottom_frame, text="Max Output Current, mA", fg="black", bg="white")
        label_9 = Label(self.bottom_frame, text="Set Input Voltage, mV", fg="black", bg="white")
        label_10 = Label(self.bottom_frame, text="Max Input Current, mA", fg="black", bg="white")
        # Place labels with grid method
        label_1.grid(row=0, column=0, sticky=N + S + E + W)
        label_2.grid(row=0, column=1, sticky=N + S + E + W)
        label_3.grid(row=0, column=2, sticky=N + S + E + W)
        label_4.grid(row=0, column=3, sticky=N + S + E + W)
        label_5.grid(row=0, column=4, sticky=N + S + E + W)
        # label_6.grid(row=0, column=5, sticky=N + S + E + W)
        label_7.grid(row=2, column=3, sticky=N + S + E + W)
        label_8.grid(row=2, column=4, sticky=N + S + E + W)
        label_9.grid(row=2, column=0, sticky=N + S + E + W)
        label_10.grid(row=2, column=1, sticky=N + S + E + W)
        # Config the fonts
        updating_label_font_size = 14
        updating_label_font_type = 'Arial'
        # Config the fonts
        label_1.config(font=(updating_label_font_type, updating_label_font_size))
        label_2.config(font=(updating_label_font_type, updating_label_font_size))
        label_3.config(font=(updating_label_font_type, updating_label_font_size))
        label_4.config(font=(updating_label_font_type, updating_label_font_size))
        label_5.config(font=(updating_label_font_type, updating_label_font_size))
        # label_6.config(font=(updating_label_font_type, updating_label_font_size))
        label_7.config(font=(updating_label_font_type, updating_label_font_size))
        label_8.config(font=(updating_label_font_type, updating_label_font_size))
        label_9.config(font=(updating_label_font_type, updating_label_font_size))
        label_10.config(font=(updating_label_font_type, updating_label_font_size))

        # Create changing labels
        self.field_input_volt = Label(self.bottom_frame, text="10", fg="black", bg="white")
        self.field_input_current = Label(self.bottom_frame, text="11", fg="black", bg="white")
        self.field_output_volt = Label(self.bottom_frame, text="12", fg="black", bg="white")
        self.field_output_current = Label(self.bottom_frame, text="13", fg="black", bg="white")

        self.field_set_input_volt = Label(self.bottom_frame, text=str(DEFAULT_INPUT_VOLTAGE * 1000), fg="black", bg="white")
        self.field_max_input_current = Label(self.bottom_frame, text=str(MAX_INPUT_CURRENT * 1000), fg="black", bg="white")
        self.field_set_output_volt = Label(self.bottom_frame, text=str(OUTPUT_VOLTAGE), fg="black", bg="white")
        self.field_max_output_current = Label(self.bottom_frame, text=str(MAX_OUTPUT_CURRENT * 1000), fg="black", bg="white")

        # self.entry_COM = Entry(self.bottom_frame, fg="black", bg="white", justify='center')
        self.entry_input_res = Entry(self.bottom_frame, fg="black", bg="white", justify='center')

        # Config the fonts
        self.field_input_volt.config(font=(updating_label_font_type, updating_label_font_size), fg="blue")
        self.field_input_current.config(font=(updating_label_font_type, updating_label_font_size), fg="red")
        self.field_output_volt.config(font=(updating_label_font_type, updating_label_font_size), fg="purple")
        self.field_output_current.config(font=(updating_label_font_type, updating_label_font_size), fg="brown")

        self.field_set_input_volt.config(font=(updating_label_font_type, updating_label_font_size), fg="blue")
        self.field_max_input_current.config(font=(updating_label_font_type, updating_label_font_size), fg="red")
        self.field_set_output_volt.config(font=(updating_label_font_type, updating_label_font_size), fg="purple")
        self.field_max_output_current.config(font=(updating_label_font_type, updating_label_font_size), fg="brown")

        # self.entry_COM.config(font=(updating_label_font_type, updating_label_font_size))
        self.entry_input_res.config(font=(updating_label_font_type, updating_label_font_size), fg="green")

        # Place labels with grid method
        self.field_input_volt.grid(row=1, column=0, sticky=N + S + E + W)
        self.field_input_current.grid(row=1, column=1, sticky=N + S + E + W)
        self.field_output_volt.grid(row=1, column=3, sticky=N + S + E + W)
        self.field_output_current.grid(row=1, column=4, sticky=N + S + E + W)

        self.field_set_input_volt.grid(row=3, column=0, sticky=N + S + E + W)
        self.field_max_input_current.grid(row=3, column=1, sticky=N + S + E + W)
        self.field_set_output_volt.grid(row=3, column=3, sticky=N + S + E + W)
        self.field_max_output_current.grid(row=3, column=4, sticky=N + S + E + W)

        # self.entry_COM.grid(row=1, column=5)
        self.entry_input_res.grid(row=1, column=2)

        # Create checkButton
        self.exp_flag = IntVar()
        self.exp_check_button = Checkbutton(self.bottom_frame, text='Experiment mode', variable=self.exp_flag,
                                            fg="black", bg="white")
        self.exp_check_button.grid(row=3, column=2)
        self.exp_check_button.config(font=(updating_label_font_type, updating_label_font_size))

        # Create Start-stop button
        # Place it
        # Configure font
        # Configure font
        # Bind a callback
        self.button_start_stop = Button(self.bottom_frame, text="Start", fg="black", bg="white")
        self.button_start_stop.grid(row=2, column=5)
        self.button_start_stop.config(font=(updating_label_font_type, updating_label_font_size))
        self.button_start_stop.bind("<Button-1>", self.button_start_stop_callback)

        # Create Start-stop button
        # Place it
        # Configure font
        # Configure font
        # Bind a callback
        self.button_clear_data = Button(self.bottom_frame, text="Clear data", fg="black", bg="white")
        self.button_clear_data.grid(row=3, column=5)
        self.button_clear_data.config(font=(updating_label_font_type, updating_label_font_size))
        self.button_clear_data.bind("<Button-1>", self.button_clear_data_callback)

        # Create Start-stop button
        # Place it
        # Configure font
        # Configure font
        # Bind a callback
        self.button_update_params = Button(self.bottom_frame, text="Update", fg="black", bg="white")
        self.button_update_params.grid(row=2, column=2)
        self.button_update_params.config(font=(updating_label_font_type, updating_label_font_size))
        self.button_update_params.bind("<Button-1>", self.update_button_callback)

        # Settings for a figure
        self.font_title_size = 16

        # Create a figure
        self.figure_1 = Figure(figsize=(16, 5), dpi=100)
        self.axes_1 = self.figure_1.add_subplot(121)
        self.axes_2 = self.figure_1.add_subplot(122)
        self.axes_1_twin = self.axes_1.twinx()
        self.axes_2_twin = self.axes_2.twinx()

        # Create containers for graphs
        self.graph_container_1 = Frame(self.master)

        # Allocate containers via grid method
        self.graph_container_1.grid(row=0, column=0, columnspan=6)

        # Create canvas
        self.canvas_graph_1 = FigureCanvasTkAgg(self.figure_1, self.graph_container_1)
        self.canvas_graph_1.draw()

        # Create widget
        self.graph_1_widget = self.canvas_graph_1.get_tk_widget()
        self.graph_1_widget.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        # Initial values for resistanses and temperatures
        # self.entry_COM.insert(0, DEFAULT_COM_PORT)
        self.entry_input_res.insert(0, DEFAULT_INPUT_RES)

        # Animation
        self.ani = animation.FuncAnimation(self.figure_1, self.animate, interval=2000)

        # Pause
        self.pause = True

        self.val_input_volt = 0
        self.val_input_current = 0
        self.val_output_volt = 0
        self.val_output_current = 0

        self.val_input_res = 0

        self.val_set_input_volt = DEFAULT_INPUT_VOLTAGE
        self.val_max_input_current = MAX_INPUT_CURRENT
        self.val_set_output_volt = OUTPUT_VOLTAGE
        self.val_max_output_current = MAX_OUTPUT_CURRENT


        # Create objects for SMU support
        self.queue = Queue.Queue()
        self.smu_thread = SmuThreadedTask(self.queue)
        self.smu_thread.start()
        self.smu_msg = [0, 0]

    def get_data_from_smu(self):
        try:
            self.smu_msg = self.queue.get(0)

            self.val_input_volt = self.smu_msg[0]
            self.val_input_current = self.smu_msg[1]
            self.val_output_volt = self.smu_msg[2]
            self.val_output_current = self.smu_msg[3]

            # Show result of the task if needed
            print("Data from SMU")

        except Queue.Empty:
            print("No new data from SMU")

    def animate(self, arg2):
        if self.pause is False:

            # Look for the data from SMU
            self.get_data_from_smu()
            # Get data from GUI
            self.get_data_from_GUI()
            # Save data
            self.save_data()

            # Check that file exists
            if not os.path.exists(self.data_file_name):
            	print("There is no file with data.")
            	return

            # Open file
            file = open(self.data_file_name, 'r')

            n = 30 * 15
            pull_data = self.tail(file, n)
            data_array = pull_data[0]

            time_val = []
            input_volt_val = []
            input_current_val = []
            output_volt_val = []
            output_current_val = []

            for eachLine in data_array:
                if len(eachLine) > 1:
                    time_of_acq, input_volt, input_current, output_volt, output_current = eachLine.split(',')
                    time_val.append(datetime.datetime.strptime(time_of_acq, '%d.%m.%Y %H:%M:%S'))
                    input_volt_val.append(float(input_volt))
                    input_current_val.append(float(input_current))
                    output_volt_val.append(float(output_volt))
                    output_current_val.append(float(output_current))

            # Convert from V to mV
            input_volt_val = [x * 1000 for x in input_volt_val]
            # output_volt_val = [x * 1000 for x in output_volt_val]
            # Convert from A to mA
            input_current_val = [x * 1000 for x in input_current_val]           
            output_current_val = [x * 1000 for x in output_current_val]

            # Plot input channel
            self.axes_1.clear()
            self.axes_1_twin.clear()
            self.axes_1.plot(time_val, input_volt_val, color="blue")
            self.axes_1_twin.plot(time_val, input_current_val, color="red")
            self.axes_1.set_title("Input channel voltages (mV) and current (mA)", fontsize=self.font_title_size)

            # Plot voutput channels
            self.axes_2.clear()
            self.axes_2_twin.clear()
            self.axes_2.plot(time_val, output_volt_val, color="purple")
            self.axes_2_twin.plot(time_val, output_current_val, color="brown")
            self.axes_2.set_title("Output channel voltages (V) and current (mA)", fontsize=self.font_title_size)

            mean_output_current = statistics.mean(output_current_val)
            mse_output_current = np.sqrt(np.square(np.subtract(output_current_val, mean_output_current)).mean()) 

            print("Mean: ", mean_output_current)
            print("MSE: ", mse_output_current)

            # Add horizontal lines to plot average current
            self.axes_2_twin.axhline(mean_output_current, linestyle='--', color="brown")
            # Add horizontal lines to voltage plot
            self.axes_2_twin.axhline(mean_output_current + mse_output_current, linestyle='--', color="brown")
            self.axes_2_twin.axhline(mean_output_current - mse_output_current, linestyle='--', color="brown")

            # Format axes for data
            self.axes_1.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%M:%S'))
            self.axes_1.tick_params(axis='x', rotation=45)
            self.axes_2.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%M:%S'))
            self.axes_2.tick_params(axis='x', rotation=45)
            self.axes_1.xaxis_date()
            self.axes_2.xaxis_date()

            # Update labels with values
            self.field_input_volt['text'] = "{:.2f}".format(float(self.val_input_volt * 1000))
            self.field_input_current['text'] = "{:.2f}".format(float(self.val_input_current * 1000))
            self.field_output_volt['text'] = "{:.2f}".format(float(self.val_output_volt))
            self.field_output_current['text'] = "{:.3f}".format(float(self.val_output_current * 1000))

            # Check if it is time to change the voltage
            # Check timeout and then check data
            if (time.time() - self.sequence_start_time > TRANSITION_TIME_SEC):

                error_percent = 2*mse_output_current/-mean_output_current * 100

                print("Error_percent: ", error_percent)

                if ((error_percent) < 10) or (error_percent < 0):
                # if True:

                    # Save last data in a separate file
                    file_name = 'Results/exp_data_' + "{:.2f}".format(self.val_input_res) + '_' + "{:.4f}".format(self.val_set_input_volt) 
                    file_name = file_name + '_' + "{:.3f}".format(self.val_max_input_current) + '_' + "{:.2f}".format(self.val_set_output_volt) + '_' + "{:.3f}".format(self.val_max_output_current) + '.txt'

                    # Check that file exists
                    if not os.path.exists(file_name):
                        file = open(file_name, 'w+')
                        file.close()

                    file = open(file_name, 'a+')
                    for eachLine in data_array:
                    	file.write(eachLine + '\n')
                    file.close()

                    # Switch the input voltage 

                    self.val_set_input_volt =  self.val_set_input_volt + 0.002

                    if self.val_set_input_volt > 0.080:
                        self.pause = True
                        return;

                    self.smu_thread.smu_set_new_input_voltage(self.val_set_input_volt)

                    # Update GUI
                    self.field_set_input_volt['text'] = "{:.2f}".format(float(self.val_set_input_volt * 1000))

                    # Reset the timer
                    self.sequence_start_time = time.time()

                    # Write to new file
                    self.update_data_file_name()


    @staticmethod
    def tail(f, n, offset=None):
        """Reads a n lines from f with an offset of offset lines.  The return
        value is a tuple in the form ``(lines, has_more)`` where `has_more` is
        an indicator that is `True` if there are more lines in the file.
        """
        avg_line_length = 67
        to_read = n + (offset or 0)

        while 1:
            try:
                f.seek(-(avg_line_length * to_read), 2)
            except IOError:
                # woops.  apparently file is smaller than what we want
                # to step back, go to the beginning instead
                f.seek(0)
            pos = f.tell()
            lines = f.read().splitlines()
            if len(lines) >= to_read or pos == 0:
                return lines[-to_read:offset and -offset or None], \
                       len(lines) > to_read or pos > 0
            avg_line_length *= 1.3

    def get_data_from_GUI(self):
    	pass

    def save_data(self):


        # Check that file exists
        if not os.path.exists(self.data_file_name):
            print("File does not exist. Creating new...")
            file = open(self.data_file_name, 'w+')
            file.close()

        time_str = datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')		

        file = open(self.data_file_name, 'a+')
        file.write(time_str + ',' + "{:.9f}".format(self.val_input_volt) + ',' + "{:.9f}".format(self.val_input_current) + ',' +
                   "{:.9f}".format(self.val_output_volt) + ',' + "{:.9f}".format(self.val_output_current) + '\n')
        file.close()

    def update_data_file_name(self):

        # # File name for data and final data
        # if self.exp_flag.get():
        #     self.data_file_name = 'Results/exp_data_' + "{:.2f}".format(self.val_input_res) + '_' + "{:.4f}".format(self.val_set_input_volt)
        #     self.data_file_name = self.data_file_name + '_' + "{:.3f}".format(self.val_max_input_current) + '_' + "{:.2f}".format(self.val_set_output_volt) + '_' + "{:.3f}".format(self.val_max_output_current) + '.txt'
        # else:
        self.data_file_name = 'Results/data_' + datetime.datetime.now().strftime('%d_%m_%Y_%H_%M') + '.txt'

    def update_button_callback(self, arg2):

        self.val_input_res = float(self.entry_input_res.get())
        self.update_data_file_name()

    def button_start_stop_callback(self, arg2):
        if self.button_start_stop['text'] == "Start":
            # Resume SMU
            self.smu_thread.resume_smu()
            self.button_start_stop['text'] = "Stop"

            self.val_input_res = float(self.entry_input_res.get())
            self.update_data_file_name()

            self.sequence_start_time = time.time()

            self.pause = False

        elif self.button_start_stop['text'] == "Stop":
            # Pause SMU
            self.smu_thread.pause_smu()
            with self.queue.mutex:
                self.queue.queue.clear()
            self.button_start_stop['text'] = "Start"
            self.pause = True

    def button_clear_data_callback(self, arg2):
        if os.path.exists(self.data_file_name):
            os.remove(self.data_file_name)
        else:
            print("The file does not exist")


root = Tk()
root.title("Testbed GUI")
root.configure(background='white')
app = App(root)

# ani = animation.FuncAnimation(app.figure_1, app.animate, interval=1000)

root.mainloop()

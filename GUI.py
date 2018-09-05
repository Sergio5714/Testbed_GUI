from tkinter import *
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.figure import Figure
import matplotlib
import matplotlib.animation as animation
import time
import sys
if sys.version_info[0] < 3:
    import Tkinter as tk
else:
    import tkinter as tk
matplotlib.use("TkAgg")


class App:
    def __init__(self, master):
        self.master = master

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
        self.bottom_frame = Frame(self.master)
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

        # Create Start-stop button
        self.button_start_stop = Button(self.bottom_frame, text="Start", fg="black", bg="white")
        # Place it
        self.button_start_stop.grid(row=3, column=1, sticky=N + S + E + W)
        # Bind a callback
        self.button_start_stop.bind("<Button-1>", output)

        # Create labels (names)
        label_1 = Label(self.bottom_frame, text="Temperature 1, C", fg="black", bg="white")
        label_2 = Label(self.bottom_frame, text="Temperature 2, C", fg="black", bg="white")
        label_3 = Label(self.bottom_frame, text="Temperature 3, C", fg="black", bg="white")
        label_4 = Label(self.bottom_frame, text="Voltage difference 1, mv", fg="black", bg="white")
        label_5 = Label(self.bottom_frame, text="Voltage difference 2, mv", fg="black", bg="white")
        label_6 = Label(self.bottom_frame, text="COM port", fg="black", bg="white")
        label_7 = Label(self.bottom_frame, text="Resistance, ohm", fg="black", bg="white")
        label_8 = Label(self.bottom_frame, text="Resistance, ohm", fg="black", bg="white")
        # Place labels with grid method
        label_1.grid(row=0, column=0, sticky=N + S + E + W)
        label_2.grid(row=0, column=1, sticky=N + S + E + W)
        label_3.grid(row=0, column=2, sticky=N + S + E + W)
        label_4.grid(row=0, column=3, sticky=N + S + E + W)
        label_5.grid(row=0, column=4, sticky=N + S + E + W)
        label_6.grid(row=2, column=0, sticky=N + S + E + W)
        label_7.grid(row=2, column=3, sticky=N + S + E + W)
        label_8.grid(row=2, column=4, sticky=N + S + E + W)

        # Create changing labels
        self.label_temp_1 = Label(self.bottom_frame, text="10", fg="black", bg="white")
        self.label_temp_2 = Label(self.bottom_frame, text="11", fg="black", bg="white")
        self.label_temp_3 = Label(self.bottom_frame, text="12", fg="black", bg="white")
        self.label_volt_1 = Label(self.bottom_frame, text="13", fg="black", bg="white")
        self.label_volt_2 = Label(self.bottom_frame, text="14", fg="black", bg="white")
        self.label_COM = Label(self.bottom_frame, text="15", fg="black", bg="white")
        self.label_res_1 = Label(self.bottom_frame, text="16", fg="black", bg="white")
        self.label_res_2 = Label(self.bottom_frame, text="17", fg="black", bg="white")
        # Place labels with grid method
        self.label_temp_1.grid(row=1, column=0, sticky=N + S + E + W)
        self.label_temp_2.grid(row=1, column=1, sticky=N + S + E + W)
        self.label_temp_3.grid(row=1, column=2, sticky=N + S + E + W)
        self.label_volt_1.grid(row=1, column=3, sticky=N + S + E + W)
        self.label_volt_2.grid(row=1, column=4, sticky=N + S + E + W)
        self.label_COM.grid(row=3, column=0, sticky=N + S + E + W)
        self.label_res_1.grid(row=3, column=3, sticky=N + S + E + W)
        self.label_res_2.grid(row=3, column=4, sticky=N + S + E + W)

        # Create a figure
        self.figure_1 = Figure(figsize=(6, 5), dpi=100)
        self.figure_2 = Figure(figsize=(6, 5), dpi=100)
        self.axes_1 = self.figure_1.add_subplot(111)
        self.axes_2 = self.figure_2.add_subplot(111)

        # Create containers for graphs
        self.graph_container_1 = Frame(self.master)
        self.graph_container_2 = Frame(self.master)

        # Allocate containers via grid method
        self.graph_container_1.grid(row=0, column=0, columnspan=3)
        self.graph_container_2.grid(row=0, column=3, columnspan=3)

        self.canvas_graph_1 = FigureCanvasTkAgg(self.figure_1, self.graph_container_1)
        self.canvas_graph_2 = FigureCanvasTkAgg(self.figure_2, self.graph_container_2)
        self.canvas_graph_1.show()
        self.canvas_graph_2.show()

        self.graph_1_widget = self.canvas_graph_1.get_tk_widget()
        self.graph_2_widget = self.canvas_graph_2.get_tk_widget()
        self.graph_1_widget.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        self.graph_2_widget.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

    def animate(self, arg2):
        pull_data = open('data.txt', 'r').read()
        data_array = pull_data.split('\n')
        time_val = []
        temp_1_val = []
        temp_2_val = []
        temp_3_val = []
        volt_1_val = []
        volt_2_val = []
        for eachLine in data_array:
            if len(eachLine) > 1:
                time, temp_1, temp_2, temp_3, volt_1, volt_2 = eachLine.split(',')
                time_val.append(int(time))
                temp_1_val.append(int(temp_1))
                temp_2_val.append(int(temp_2))
                temp_3_val.append(int(temp_3))
                volt_1_val.append(int(volt_1))
                volt_2_val.append(int(volt_2))

        self.axes_1.clear()
        self.axes_1.plot(time_val, temp_1_val)
        self.axes_1.plot(time_val, temp_2_val)
        self.axes_1.plot(time_val, temp_3_val)
        self.axes_1.plot(time_val, volt_1_val)
        self.axes_1.plot(time_val, volt_2_val)


def output(event):
    txt = entry_1.get()
    try:
        if int(txt) < 18:
            label_1["text"] = 'Go HOME'
        else:
            label_1["text"] = 'Andrey'
    except ValueError:
        label_1["text"] = 'Wrong value'


def update_graphs():
    app.animate()
    root.after(1000, update_graphs)


root = Tk()
root.title("Testbed GUI")
app = App(root)

ani = animation.FuncAnimation(app.figure_1, app.animate, interval=1000)
#update_graphs()
# update_clock()
root.mainloop()

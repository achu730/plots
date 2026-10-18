sheet = data["Sheet1"]

t = sheet["Time (seconds)"]
t_err = sheet["Time error (seconds)"]
y = sheet["Y-displacement(meters)"]
y_err = sheet["Y-displacement error (meters)"]

fig, ax = pw.figure()

ax.errorbar(t, y, xerr=t_err, yerr=y_err, **pw.data_style(0), label="Data")

# Quadratic (degree-2 polynomial) least-squares fit of the plotted points.
# The first point has a zero y uncertainty, so the fit is unweighted (no yerr).
# show_equation=True writes the fitted equation and R² into the legend.
n_lines_before = len(ax.lines)
fit = pw.fit(ax, t, y, kind="poly", degree=2, label="Quadratic fit", show_equation=True)

# Make the fitted trendline red and dotted, and keep it behind the data points.
for line in ax.lines[n_lines_before:]:
    line.set_color("red")
    line.set_linestyle(":")
    line.set_zorder(1)

ax.set_xlabel(pw.label("Time", "s"))
ax.set_ylabel(pw.label("Vertical displacement", "m"))

pw.legend(ax)

# This is a ball-tracking measurement, not LHCb data, so the LHCb label is left off.
sheet = data["Sheet1"]

t = sheet["Time (seconds)"]
y = sheet["Y-displacement(meters)"]
t_err = sheet["Time error (seconds)"]
y_err = sheet["Y-displacement error (meters)"]

fig, ax = pw.figure()

data_kw = pw.data_style(0)
data_kw.update(zorder=3)  # keep data points drawn on top of the fit curve
ax.errorbar(t, y, xerr=t_err, yerr=y_err, **data_kw, label="Data")

pw.fit(ax, t, y, kind="poly", degree=2, yerr=y_err, label="2nd-order polynomial fit",
       show_equation=True)

ax.set_xlabel(pw.label("Time", "s"))
ax.set_ylabel(pw.label("Vertical displacement", "m"))

pw.legend(ax, loc="upper left")
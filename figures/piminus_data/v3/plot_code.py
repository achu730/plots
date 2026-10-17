x = df["piminus_1_OWNPV_Z"].to_numpy()
y = df["piminus_1_P"].to_numpy()

fig, ax = pw.figure()

kw = pw.data_style(0)
kw.update(linestyle="none", ms=0.8, alpha=0.5)
ax.errorbar(x, y, **kw, label=r"$\pi^{-}$ candidates")

ax.set_xlabel(pw.label(r"Own primary vertex $z$", "mm"))
ax.set_ylabel(pw.label(r"$\pi^{-}$ momentum $p$", r"MeV/$c$"))
ax.minorticks_on()

pw.legend(ax)
pw.experiment_label(ax)
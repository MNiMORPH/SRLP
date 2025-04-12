import numpy as np
from matplotlib import pyplot as plt
plt.ion()

import srlp

S0 = 0.003
P_xB = 0.2
z1 = 0

Qamp = 0.5
dt = 3.15E7 * 1E2
nt = int(100)
Bmax = 250.

lp = srlp.LongProfile()
self = lp

self.bcr = z1
lp.set_niter(3)
lp.set_D(1E-3) # 1 mm 
lp.set_Mannings_roughness(0.02) # .02? .025?
lp.set_Darcy_Weisbach_friction(0.1)
lp.set_tau_crit_bank(2) # 2 Pa

lp.basic_constants()
lp.sediment_lumped_constants()
lp.set_hydrologic_constants()

lp.set_x(dx=500, nx=180, x0=10E3)
lp.set_z(S0=-S0, z1=z1)
lp.set_A(k_xA=1.)
lp.set_Q(k_xQ=1.433776163432246e-05, P_xQ=7/4.*0.7)
#lp.set_Q(10.)
lp.set_B(k_xB=Bmax/np.max(lp.x**P_xB), P_xB=P_xB)
lp.set_z_bl(z1)
Qs0 = lp.k_Qs * lp.Q[0] * S0**(5/6.)
lp.set_Qs_input_upstream(Qs0)

fig = plt.figure(figsize=(6,3))
ax1 = fig.add_subplot(1,1,1)
plt.xlabel('Downstream distance [km]', fontsize=14, fontweight='bold')
plt.ylabel('Elevation [m]', fontsize=14, fontweight='bold')
plt.tight_layout()

# Starting case
lp.set_uplift_rate(0)
lp.evolve_threshold_width_river(10, 1E14)
ax1.plot(lp.x/1000., lp.z, color='.5', linewidth=3)
#lp.evolve_threshold_width_river(100, 1E10)
#ax1.plot(lp.x/1000., lp.z, color='0', linewidth=3)

# Base level fall
#lp.set_z_bl(-50)
# Sediment supply increase
Qs0 = 2. * lp.k_Qs * lp.Q[0] * S0**(5/6.)
lp.set_Qs_input_upstream(Qs0)
for i in range(15*5):
    lp.evolve_threshold_width_river(1, 3E10)
    if i % 5 == 0:
        ax1.plot(lp.x/1000., lp.z, color='.5', linewidth=1, alpha=.5)

# New equilibrium
#lp.evolve_threshold_width_river(1, 1E14)
#ax1.plot(lp.x/1000., lp.z - lp.z[0] + 500, color='0', linewidth=3)



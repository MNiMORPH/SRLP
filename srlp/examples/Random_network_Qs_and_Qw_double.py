# ------------------------------------------------------------------------------
# Simple example to set up, plot and evolve a randomly generated network in
# SRLP.
# ------------------------------------------------------------------------------

# ---- Import packages
import srlp
import build_synthetic_network
import matplotlib.pyplot as plt


# ---- Network properties

# Number of channel heads
magnitude = 20

# Distance from mouth to head of longest stream
L = 100.e3

# How to divide up segments
approx_dx = 5.e2 # will try to divide segments into evenly space points with
                 # roughly this dx.
min_nx = 5       # will put at least this many points in each segment

# Average discharge, sediment-to-water ratio
mean_discharge = 10.
water_to_sediment_ratio = 1.e4

# Valley width
width = 100.

# Parameters required for sand-bed rivers SRLP
D = 0.5E-3        # 0.5 mm 
n = 0.025         # 0.025 or 0.02
C_f = 0.1
tau_crit_bank = 2 # 2 Pa


# ---- Set up the network
net, net_topo = build_synthetic_network.generate_random_network(
    magnitude=magnitude,
    max_length=L,
    approx_dx=approx_dx,
    min_nxs=min_nx,
    mean_discharge=mean_discharge,
    sediment_discharge_ratio=water_to_sediment_ratio,
    mean_width=width, ## width changed to mean_width, by NI.
    D=D, n=n, C_f=C_f, tau_crit_bank=tau_crit_bank,
    evolve=True # evolve the network for a while (aiming for stready state)
    )

# ---- Compute some properties of the network, e.g. Horton ratios
net.compute_network_properties()

# ---- Make a quick schematic plot of the network planform
__ = build_synthetic_network.plot_network(net)

# ---- Plot the long profile
# Note everywhere has the same Qs/Q ratio, so all the segments have the same
# slope
for seg in net.list_of_LongProfile_objects:
    plt.plot(seg.x/1.e3, seg.z)
plt.xlabel("Downstream distance [km]")
plt.ylabel("Elevation [m]")
plt.show()

# ---- Double sediment supply

# First plot the old profile for comparison
for seg in net.list_of_LongProfile_objects:
    plt.plot(seg.x/1.e3, seg.z, ":")

# For now there is no mechanism in the Network class to set directly the
# sediment supply - we can only set the slope at the upstream boundary. So we
# need to raise our desired scaling to the power 6/7.
# Here I loop over the network channel heads to make a list of new slopes, each
# 2^(6/7) the old slope - effectively doubling the sediment supply.
new_S0 = [
    net.list_of_LongProfile_objects[i].S0*(2.**(6./7.))
        for i in net.list_of_channel_head_segment_IDs
    ]
net.update_z_ext_external_upstream(S0 = new_S0)

# Evolve for a while
net.evolve_threshold_width_river_network(nt=10, dt=3.15e10)

# Plot the new profiles
for seg in net.list_of_LongProfile_objects:
    plt.plot(seg.x/1.e3, seg.z)
plt.xlabel("Downstream distance [km]")
plt.ylabel("Elevation [m]")
plt.show()

# ---- Double water supply

# First plot the old profile for comparison
for seg in net.list_of_LongProfile_objects:
    plt.plot(seg.x/1.e3, seg.z, ":")

# As with sediment supply, there is currently not a neat way to change
# discharge.
# We need to change the slope at the channel heads as before (this time to
# double water supply we need to change slope by a factor 0.5^(6/7)).
new_S0 = [
    net.list_of_LongProfile_objects[i].S0*(0.5**(6./7.))
        for i in net.list_of_channel_head_segment_IDs
    ]
net.update_z_ext_external_upstream(S0 = new_S0)

# We also need to update discharge on all the segments.
# I copied this chunk from the 'initialize' function, where it sets the
# discharge.
new_Q = [seg.Q*2. for seg in net.list_of_LongProfile_objects]
net.update_Q(new_Q)
net.create_Q_ext_lists()
net.update_Q_ext_from_Q()
net.update_Q_ext_internal()
net.update_Q_ext_external_upstream() 
net.update_Q_ext_external_downstream()
net.update_dQ_ext_2cell()

# Evolve for a while
net.evolve_threshold_width_river_network(nt=10, dt=3.15e10)

# Plot the new profiles
for seg in net.list_of_LongProfile_objects:
    plt.plot(seg.x/1.e3, seg.z)
plt.xlabel("Downstream distance [km]")
plt.ylabel("Elevation [m]")
plt.show()
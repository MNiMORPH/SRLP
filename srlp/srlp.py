import numpy as np
from matplotlib import pyplot as plt
from scipy.sparse import spdiags, identity, block_diag
from scipy import sparse
from scipy.sparse.linalg import spsolve, isolve
from scipy.stats import linregress
import warnings
import sys

class LongProfile(object):
    """
    SAND-bed river long-profile solution builder and solver
    """

    def __init__(self):
        self.z = None
        self.x = None
        self.A = None
        self.Q = None
        self.B = None
        self.D = None # Grain size; needed only to resolve width and depth
        self.b = None # Width and depth need not be resoloved to compute
        self.h = None # long-profile evolution
        self.S0 = None # S0 for Q_s_0 where there is a defined boundary input
        self.dx_ext = None
        self.dx_2cell = None
        self.Q_s_0 = None
        self.z_bl = None
        self.ssd = 0. # distributed sources or sinks
        self.sinuosity = 1.
        self.intermittency = 1.
        self.t = 0
        self.upstream_segment_IDs = []
        self.downstream_segment_IDs = []
        self.ID = None
        self.downstream_fining_subsidence_equivalent = 0.
        #self.gravel_fractional_loss_per_km = None ## COMMENTED OUT by N. sand-beds
        #self.downstream_dx = None # not necessary if x_ext given
        #self.basic_constants()

        # Constants for sand-bed rivers (set later)
        self.tau_crit_bank = None # Critical stress to erode mud banks
        self.C_f = None # Darcy-Weisbach friction factor
        self.n = None # Manning's roughness ## Added by N

    def set_ID(self, ID):
        """
        Set the ID of this segment
        """
        self.ID = ID

    def set_upstream_segment_IDs(self, upstream_segment_IDs):
        """
        Set a list of ID numbers assigned to upstream river segments
        Requires list or None input
        """
        self.upstream_segment_IDs = upstream_segment_IDs

    def set_downstream_segment_IDs(self, downstream_segment_IDs):
        """
        Set a list of ID numbers assigned to downstream river segments
        Requires list or None input
        """
        self.downstream_segment_IDs = downstream_segment_IDs

    #def set_downstream_dx(self, downstream_dx)
    #    """
    #    Downstream dx, if applicable, for linking together segments in a
    #    network. This could be part of x_ext
    #    """
    #    self.downstream_dx = downstream_dx

    def basic_constants(self):
        self.lambda_p = 0.35
        self.rho_s = 2650.
        self.rho = 1000.
        self.R = (self.rho_s - self.rho) / self.rho
        self.g = 9.805
        self.epsilon = 0.2 # Parker channel criterion
        self.tau_star_c = 0.0495
        self.phi = 3.97 # coefficient for Wong and Parker MPM

    def set_Darcy_Weisbach_friction(self, C_f):
        self.C_f = C_f

    def set_Mannings_roughness(self, n): ## ADDED by N
        self.n = n 
    
    def set_tau_crit_bank(self, tau_crit_bank):
        self.tau_crit_bank = tau_crit_bank
        
    def set_D(self, D):
        self.D = D
    
    def sediment_lumped_constants(self): ## CHANGED by N
        self.k_Qs = (0.05 / self.n) * 1/( self.g**.5 * self.R**2 ) * \
                    ( ( 1 + self.epsilon) * self.tau_crit_bank / \
                      ( self.rho * self.g ) )**(7/6.) * (1/self.D)

    def set_hydrologic_constants(self, P_xA=7/4., P_AQ=0.7, P_xQ=None):
        self.P_xA = P_xA # inverse Hack exponent
        self.P_AQ = P_AQ # drainage area -- discharge exponent
        if P_xQ:
            warnings.warn("P_xQ may be inconsistent with P_xA and P_AQ")
            self.P_xQ = P_xQ
        else:
            self.P_xQ = P_xA * P_AQ

    def set_intermittency(self, I):
        self.intermittency = I

    def set_x(self, x=None, x_ext=None, dx=None, nx=None, x0=None):
        """
        Set x directly or calculate it.
        Pass one of three options:
        x alone
        x_ext alone (this will also define x)
        dx, nx, and x0
        """
        if x is not None:
            # This doesn't have enough information to work consistently
            # Needs ext
            self.x = np.array(x)
            self.dx = np.diff(self.x)
            self.dx_2cell = self.x[2:] - self.x[:-2]
        elif x_ext is not None:
            self.x_ext = np.array(x_ext)
            self.x = x_ext[1:-1]
            self.dx_ext = np.diff(self.x_ext)
            self.dx_ext_2cell = self.x_ext[2:] - self.x_ext[:-2]
            self.dx_2cell = self.x[2:] - self.x[:-2]
            self.dx = np.diff(self.x)
        elif (dx is not None) and (nx is not None) and (x0 is not None):
            self.x = np.arange(x0, x0+dx*nx, dx)
            self.x_ext = np.arange(x0-dx, x0+dx*(nx+1), dx)
            self.dx = dx * np.ones(len(self.x) - 1)
            self.dx_ext = dx * np.ones(len(self.x) + 1)
            self.dx_2cell = np.ones(len(self.x) - 1)
            self.dx_ext_2cell = self.x_ext[2:] - self.x_ext[:-2]
        else:
            sys.exit("Need x OR x_ext OR (dx, nx, x0)")
        self.nx = len(self.x)
        self.L = self.x_ext[-1] - self.x_ext[0]
        if (nx is not None) and (nx != self.nx):
            warnings.warn("Choosing x length instead of supplied nx")

    def set_z(self, z=None, z_ext=None, S0=None, z1=0):
        """
        Set z directly or calculate it
        S0 = initial slope (negative for flow from left to right)
             unlike in the paper, this is a dz/dx value down the valley,
             so we account for sinuosity as well at the upstream boundary.
        z1 = elevation value at RHS
        """
        if z is not None:
            self.z = z
            self.z_ext = np.hstack((2*z[0]-z[1], z, 2*z[-1]-z[-2]))
        elif z_ext is not None:
            self.z_ext = z_ext
            self.z = z_ext[1:-1]
        elif self.x.any() and self.x_ext.any() and (S0 is not None):
            self.z = self.x * S0 + (z1 - self.x[-1] * S0)
            self.z_ext = self.x_ext * S0 + (z1 - self.x[-1] * S0)
            #print self.z_ext
        else:
            sys.exit("Error defining variable")
        #self.dz = self.z_ext[2:] - self.z_ext[:-2] # dz over 2*dx!

    def set_A(self, A=None, A_ext=None, k_xA=None, P_xA=None):
        """
        Set A directly or calculate it
        """
        if A is not None:
            self.A = A
            self.A_ext = np.hstack((2*A[0]-A[1], A, 2*A[-1]-A[-2]))
        elif A_ext is not None:
            self.A_ext = A_ext
            self.A = self.A_ext[1:-1]
        elif self.x.any() and self.x_ext.any():
            self.k_xA = k_xA
            if P_xA:
                self.P_xA = P_xA
            self.A_ext = self.k_xA * self.x_ext**self.P_xA
            self.A = self.k_xA * self.x**self.P_xA
        else:
            sys.exit("Error defining variable")

    def set_Q(self, Q=None, Q_ext=None, q_R=None, A_R=None, P_AQ=None,
              k_xQ=None, P_xQ=None, update_Qs_input=True):
        """
        Set Q directly or calculate it
        q_R = storm rainfall rate [m/hr]
        """
        if k_xQ is not None:
            self.k_xQ = k_xQ
        if Q is not None:
            # Check if it is a scalar or an array
            if hasattr(Q, "__iter__"):
                self.Q = Q
            else:
                # Assuming "x" is known already
                self.Q = Q * np.ones(self.x.shape)
            # Have to be able to pass Q_ext, created with adjacencies
            # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            Q_ext = np.hstack( (2*self.Q[0]-self.Q[1],
                                self.Q,
                                2*self.Q[-1]-self.Q[-2]) )
        elif Q_ext is not None:
            self.Q = Q_ext[1:-1]
        elif q_R and A_R:
            if P_AQ:
                self.P_AQ = P_AQ
            q_R = q_R/3600. # to m/s
            Q_ext = q_R * np.minimum(A_R, self.A_ext) \
                    * (self.A_ext/np.minimum(A_R,self.A_ext))**self.P_AQ
            self.Q = Q_ext[1:-1]
        elif self.x.any() and self.x_ext.any() and k_xQ and P_xQ:
            self.Q = k_xQ * self.x**P_xQ
            Q_ext = k_xQ * self.x_ext**P_xQ
        else:
            sys.exit("Error defining variable")
        # dQ over 2*dx!
        # See Eq. D3 in Wickert & Schildgen (2019)
        # This then combines with the 1/4 factor in the coefficients
        # for the stencil that results from (2*dx)**2
        self.dQ = Q_ext[2:] - Q_ext[:-2]
        # Keep sediment supply tied to water supply, except
        # by changing S_0, to only turn one knob for one change (Q/Qs)
        if update_Qs_input:
            if self.Q_s_0:
                self.set_Qs_input_upstream(self.Q_s_0)

    def set_B(self, B=None, k_xB=None, P_xB=None):
        """
        Set B directly or calculate it: B = k_xB * x**P_xB
        """
        if B is not None:
            # Check if it is a scalar or an array
            if hasattr(B, "__iter__"):
                self.B = B
            else:
                # Assuming "x" is known already
                self.B = B * np.ones(self.x.shape)
        elif k_xB and self.x.any() and self.x_ext.any():
            self.B = k_xB * self.x**P_xB
            self.k_xB = k_xB
            self.P_xB = P_xB

    def set_uplift_rate(self, U):
        """
        Uplift rate if positive -- or equivalently, rate of base-level fall
        Subsidence (or base-level rise) accomplished by negative uplift
        """
        # Keeping sign positive now and including as adding to river
        # instead of dropping base level
        self.U = U # not sure this is the best -- flipping the sign

    def set_source_sink_distributed(self, ssd):
        self.ssd = ssd


#    def set_Sternberg_gravel_loss(self, gravel_fractional_loss_per_km=None ):   ## This block COMMENTED OUT by N.
#        """
#        Based on Dingle et al. (2017).
#        """
#        """
#        distance_downstream_from_boundary = self.x - self.x[0]
#        gravel_input = self.Q_s_0 * \
#                       np.exp( -gravel_fractional_loss_per_km/1000. 
#                                * distance_downstream_from_boundary)
#        # Q_s_0 may cause it to break; perhaps just consider Q_s[0]
#        self.downstream_fining_subsidence_equivalent = np.hstack((
#                0, np.diff(gravel_input) / ( (1-self.lambda_p) * self.B[1:] )
#                ))
#        """
#        # Use finite difference
#        # Though this is now separated from the implicit solution
#        # Must include in semi-implicit by iterating through calls to this
#        if gravel_fractional_loss_per_km is not None:
#            self.gravel_fractional_loss_per_km = gravel_fractional_loss_per_km
#        elif self.gravel_fractional_loss_per_km is not None:
#            pass
#        else:
#            raise ValueError('You must define gravel_fractional_loss_per_km.')
#        self.compute_Q_s()
#        self.downstream_fining_subsidence_equivalent = \
#                - self.gravel_fractional_loss_per_km * self.Q_s \
#                / ( (1-self.lambda_p) * self.B )

    def set_niter(self, niter=3):  ## ADDED again by N
        self.niter = niter

    def set_Qs_input_upstream(self, Q_s_0):
        """
        S0, the boundary-condition slope, is set as a function of Q_s_0.
        Note that here I use S in a different sense than in the paper:
        sinuosity is external to S here, meaning that it has to be included
        explicitly in the equation to compute S0. This is so S0 impacts
        dz/dx|boundary directly, instead of needing to be modulated each time.
        """
        self.Q_s_0 = Q_s_0
        # Q[0] is centerpoint of S?
        self.S0 = - np.sign(self.Q[0]) * self.sinuosity * \
                      ( np.abs(Q_s_0) / 
                        ( self.k_Qs * self.intermittency 
                              * np.abs(self.Q[0])) )**(6/5.)   ## ADDED **(6/5.) Double check!
        # Give upstream cell the same width as the first cell in domain
        self.z_ext[0] = self.z[0] - self.S0 * self.dx_ext[0]

    def update_z_ext_0(self):
        # Give upstream cell the same width as the first cell in domain
        self.z_ext[0] = self.z[0] - self.S0 * self.dx_ext[0]

    def compute_coefficient_time_varying(self):
        if self.S0 is not None:
            self.update_z_ext_0()
        self.dzdx_0_16 = np.abs( (self.z_ext[2:] - self.z_ext[:-2]) \
                         / self.dx_ext_2cell )**(-1/6.)
        self.C1 = self.C0 * self.dzdx_0_16 * self.Q / self.B # This part added again by N. and changed to -1/6
        # Handling C1 for networked rivers
        # Need to link the two segments without skipping the channel head
        # DOESN'T SEEM TO CHANGE ANYTHING!
        # Looks right when both are 0! Any accidental inclusion of its own
        # ghost-node Qs,in?
        if len(self.downstream_segment_IDs) > 0:
            self.C1[-1] = self.C0[-1] \
                          * (np.abs(self.z_ext[-2] - self.z_ext[-1]) \
                                   /self.dx[-1])**(-1/6.) \
                          * self.Q[-1] / self.B[-1]
        # This one matters! The above doesn't!!!! (Maybe.)
        # WORK HERE. If turns to 0, fixed. But why? Stays at initial profile?
        if len(self.upstream_segment_IDs) > 0:
            self.C1[0] = self.C0[0] \
                          * (np.abs(self.z_ext[1] - self.z_ext[0]) \
                                   /self.dx[0])**(-1/6.) \
                          * self.Q[0] / self.B[0]  # Added full C1[-1] and C1[0] eqns from grlp and changed to -1/6

    def set_z_bl(self, z_bl):
        """
        Set the right-hand Dirichlet boundary conditions, i.e. the base level,
        given in the variable "z_bl" (elevation, base level)
        """
        self.z_bl = z_bl
        self.z_ext[-1] = self.z_bl

    def set_bcr_Dirichlet(self):  # Changed by N. 7/3 from grlp to 5/3
        self.bcr = self.z_bl * ( self.C1[-1] * 5/3. \
                       * (1/self.dx_ext[-2] + 1/self.dx_ext[-1])/2. \
                       + self.dQ[-1]/self.Q[-1] )

    def set_bcl_Neumann_RHS(self):
        """
        Boundary condition on the left (conventionally upstream) side of the
        domain.

        This is for the RHS of the equation as a result of the ghost-node
        approach for the Neumann upstream boundary condition with a prescribed
        transport slope.

        This equals 2*dx * S_0 * left_coefficients
        (2*dx is replaced with the x_ext{i+1} - x_ext{i-1} for the irregular
        grid case)
        """
        # Give upstream cell the same width as the first cell in domain
        # 2*dx * S_0 * left_coefficients
        self.bcl = self.dx_ext_2cell[0] * self.S0 * \
                            - self.C1[0] * ( 5/3./self.dx_ext[0]
                            - self.dQ[0]/self.Q[0]/self.dx_ext_2cell[0] )  # Changed by N. 7/3 grom grlp to 5/3

    def set_bcl_Neumann_LHS(self):
        """
        Boundary condition on the left (conventionally upstream) side of the
        domain.

        This changes the right diagonal on the LHS of the equation using a
        ghost-node approach by defining a boundary slope that is calculated
        as a function of input water-to-sediment supply ratio.

        LHS = coeff_right at 0 + coeff_left at 0, with appropriate dx
              for boundary (already supplied)
        """
        self.right[0] = -self.C1[0] * 5/3. \
                         * (1/self.dx_ext[0] + 1/self.dx_ext[1])

    def evolve_threshold_width_river(self, nt=1, dt=3.15E7):
        """
        Solve the triadiagonal matrix through time, with a given
        number of time steps (nt) and time-step length (dt)
        """
        if (len(self.upstream_segment_IDs) > 0) or \
           (len(self.downstream_segment_IDs) > 0):
            warnings.warn("Unset boundary conditions for river segment"+
                          "in network.\n"+
                          "Local solution on segment will not be sensible.")
        self.nt = nt
        self.build_LHS_coeff_C0(dt)
        self.set_z_bl(self.z_bl)
        for ti in range(int(self.nt)):
            self.zold = self.z.copy()
            for i in range(self.niter): # Changed by N. Added from grlp again
                # If I want to keep this, will have to add to the networked
                # river too
            #    if self.gravel_fractional_loss_per_km is not None:  ## COMMENTED OUT by N
            #        self.set_Sternberg_gravel_loss()
                self.build_matrices()
                self.z_ext[1:-1] = spsolve(self.LHSmatrix, self.RHS)
                #print self.bcl
            self.t += self.dt
            self.z = self.z_ext[1:-1].copy()
            self.dz_dt = (self.z - self.zold)/self.dt
            self.Qs_internal = 1/(1-self.lambda_p) * np.cumsum(self.dz_dt) \
                                * self.B + self.Q_s_0
            if self.S0 is not None:
                self.update_z_ext_0()

    def build_LHS_coeff_C0(self, dt=3.15E7):
        """
        Build the LHS coefficient for the tridiagonal matrix.
        This is the "C0" coefficient, which is likely to be constant and
        uniform unless there are dynamic changes in width (epsilon_0 in
        k_Qs), sinuosity, or intermittency, in space and/or through time

        See eq. D3. "1/4" subsumed into "build matrices".
        For C1 (other function), Q/B included as well.
        """
        self.dt = dt # Needed to build C0, C1
        self.C0 = self.k_Qs * self.intermittency \
                    / ((1-self.lambda_p) * self.sinuosity**(5/6.)) \
                    * self.dt / self.dx_ext_2cell  # Changed by N from 7/6 grlp to 5/6

    def build_matrices(self):
        """
        Build the tridiagonal matrix (LHS) and the RHS matrix for the solution
        """
        self.compute_coefficient_time_varying()
        self.left = -self.C1 * ( (5/3.)/self.dx_ext[:-1]
                        - self.dQ/self.Q/self.dx_ext_2cell )
        self.center = -self.C1 * ( (5/3.) \
                              * (-1/self.dx_ext[:-1] \
                                 -1/self.dx_ext[1:]) ) \
                                 + 1.
        self.right = -self.C1 * ( (5/3.)/self.dx_ext[1:] # REALLY?
                        + self.dQ/self.Q/self.dx_ext_2cell )  # self.left/center/right changed by N. from 7/3 to 5/3
        # Apply boundary conditions if the segment is at the edges of the
        # network (both if there is only one segment!)
        if len(self.upstream_segment_IDs) == 0:
            #print self.dx_ext_2cell
            self.set_bcl_Neumann_LHS()
            self.set_bcl_Neumann_RHS()
        else:
            self.bcl = 0. # no b.c.-related changes
        if len(self.downstream_segment_IDs) == 0:
            self.set_bcr_Dirichlet()
        else:
            self.bcr = 0. # no b.c.-related changes
        self.left = np.roll(self.left, -1)
        self.right = np.roll(self.right, 1)
        self.diagonals = np.vstack((self.left, self.center, self.right))
        self.offsets = np.array([-1, 0, 1])
        self.LHSmatrix = spdiags(self.diagonals, self.offsets, len(self.z),
                            len(self.z), format='csr')
        self.RHS = np.hstack(( self.bcl+self.z[0],
                               self.z[1:-1],
                               self.bcr+self.z[-1])) \
                               + self.ssd * self.dt \
                               + self.downstream_fining_subsidence_equivalent \
                                      *self.dt \
                               + self.U * self.dt

    def analytical_threshold_width(self, P_xQ=None, x0=None, x1=None,
                                   z0=None, z1=None):
        """
        Analytical: no uplift
        """
        if x0 is None:
            x0 = self.x[0]
        if x1 is None:
            x1 = self.x[-1]
        if z0 is None:
            z0 = self.z[0]
        if z1 is None:
            z1 = self.z[-1]
        if P_xQ is None:
            P_xQ = self.P_xQ
        #print P_xQ
        #self.zanalytical2 = (z1 - z0) * (self.x**e - x0**e)/(x1**e - x0**e) + z0
        self.P_a = 1 - 6*P_xQ/5. # beta # Chaned by N. to 6*P_xQ/5
        self.k_a = 1/(x1**self.P_a - x0**self.P_a) * (z1 - z0) # alpha
        self.c_a = z0 - x0**self.P_a/(x1**self.P_a - x0**self.P_a) * (z1 - z0) # gamma
        self.zanalytical = self.k_a * self.x**self.P_a + self.c_a
        return self.zanalytical

    def analytical_threshold_width_perturbation(self, P_xQ=None, x0=None, x1=None,
                                   z0=None, z1=None, U=None):
        if x0 is None:
            x0 = self.x[0]
        if x1 is None:
            x1 = self.x[-1]
        if z0 is None:
            z0 = self.z[0]
        if z1 is None:
            z1 = self.z[-1]
        if P_xQ is None:
            P_xQ = self.P_xQ
        if U is None:
            U = self.U
        # Base state coefficients (no perturbation)
        #self.P_a = 1 - 6*P_xB/7. # beta
        #self.k_a = (z1 - z0)/(x1**self.P_a - x0**self.P_a) # alpha
        #self.c_a = z0 - x0**self.P_a/(x1**self.P_a - x0**self.P_a) * (z1 - z0) # gamma
        # Coefficients
        K = self.k_Qs * self.sinuosity * self.intermittency \
            / (1 - self.lambda_p) \
            * abs(self.k_a * self.P_a)**(-1/6.) \
            * self.k_xQ / self.k_xB  # Changed by N. from 1/6 to -1/6
        P = self.P_xQ
        print(P)
        # Constants of integration
        #c1 = self.U * (x0**(P+2) - x1**(P+2)) / (K*(P-2)*(self.P_a + P - 2) \
        #     + (x1**self.P_a - x0**self.P_a) / self.P_a
        #     - z1
        c1 = ( self.U * (x0**(P+2) - x1**(P+2)) / (K*(P-2)*(self.P_a + P - 2)) \
               + z0 - z1 ) \
             / ( (x0**self.P_a - x1**self.P_a) / self.P_a )
        c2 = - (c1 * x1**self.P_a)/self.P_a \
             + (U * x1**(2-P))/(K * (P-2) * (self.P_a + P - 2)) + z1
        self.zanalytical = c1 * self.x**self.P_a / self.P_a \
            - self.U * self.x**(2-P) / (K * (P-2) * (self.P_a + P - 2)) \
            + c2

    #def analytical_threshold_width_perturbation_2(self):
    #    self.analytical_threshold_width()

    def compute_Q_s(self):
        self.S = np.abs( (self.z_ext[2:] - self.z_ext[:-2]) /
                         (self.dx_ext_2cell) ) / self.sinuosity
        self.Q_s = -np.sign( self.z_ext[2:] - self.z_ext[:-2] ) \
                   * self.k_Qs * self.intermittency * self.Q * self.S**(5/6.)  # Changed by N. 7/6 to S**(5/6.)

### THIS PART commented out!! (still is) and changed by N S**(5/6.)
#    def compute_channel_width(self): 
#        if self.D is not None:
#            self.b = 0.17 / ( self.g**.5
#                              * ((self.rho_s - self.rho)/self.rho)**(5/3.)
#                              * (1+self.epsilon)**(5/3.)
#                              * (self.tau_star_c**(5/3.)) ) \
#                            * self.Q * self.S**(5/6.) / self.D**1.5
#        else:
#            raise ValueError('Set grain size to compute channel width.')
            
    def compute_flow_depth(self):
        if self.D is not None:
            self.h = (self.rho_s - self.rho)/self.rho * (1+self.epsilon) \
                        * self.tau_star_c * self.D / self.S
        else:
            raise ValueError('Set grain size to compute channel depth.')

    def slope_area(self, verbose=False):
        self.S = np.abs( (self.z_ext[2:] - self.z_ext[:-2]) \
                         / self.dx_ext_2cell )
        logS = np.log10(self.S)
        logA = np.log10(self.A)
        out = linregress(logA[1:-1], logS[1:-1]) # remove edge effects
        self.theta = -out.slope
        self.ks = 10.**out.intercept
        self.thetaR2 = out.rvalue**2.
        if verbose:
            print("Concavity = ", self.theta)
            print("k_s = ", self.ks)
            print("R2 = ", out.rvalue**2.)

# Deleted functions by A and N earlier at dogwood:
#def compute_diffusivity(self):
#def compute_equilibration_time(self):
#def compute_e_folding_time(self, n):
#def compute_wavenumber(self, n):
#def compute_series_coefficient(self, n, period):
#def compute_z_series_terms(self, period, nsum):
#def compute_Qs_series_terms(self, period, nsum):
#def compute_z_gain(self, period, nsum=100):
#def compute_Qs_gain(self, period, A_Qs=0., A_Q=0., nsum=100):
#def compute_z_lag(self, period, nsum=100):
#def compute_Qs_lag(self, period, A_Qs=0., A_Q=0., nsum=1000):


# class Network(object): ## DELETED by N.
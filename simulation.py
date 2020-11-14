import importlib
import numpy as np
import matplotlib
try:
    matplotlib.rcParams['mpl_toolkits.legacy_colorbar'] = False
except KeyError:
    pass
import matplotlib.pyplot as plt
import json
import advection.advective_fluxes as flx
import mesh.patch as patch
from simulation_null import NullSimulation, grid_setup, bc_setup
import particles.particles as particles
import util.plot_tools as plot_tools
from bokeh.io import show
from bokeh.plotting import figure
from bokeh.palettes import Viridis256
class Simulation(NullSimulation):

    def initialize(self):
        """
        Initialize the grid and variables for advection and set the initial
        conditions for the chosen problem.
        """

        my_grid = grid_setup(self.rp, ng=4)

        # create the variables
        my_data = patch.CellCenterData2d(my_grid)
        bc = bc_setup(self.rp)[0]
        my_data.register_var("density", bc)
        my_data.create()

        self.cc_data = my_data

        if self.rp.get_param("particles.do_particles") == 1:
            n_particles = self.rp.get_param("particles.n_particles")
            particle_generator = self.rp.get_param("particles.particle_generator")
            self.particles = particles.Particles(self.cc_data, bc, n_particles, particle_generator)

        # now set the initial conditions for the problem
        problem = importlib.import_module("advection.problems.{}".format(self.problem_name))
        problem.init_data(self.cc_data, self.rp)

    def method_compute_timestep(self):
        """
        Compute the advective timestep (CFL) constraint.  We use the
        driver.cfl parameter to control what fraction of the CFL
        step we actually take.
        """

        cfl = self.rp.get_param("driver.cfl")

        u = self.rp.get_param("advection.u")
        v = self.rp.get_param("advection.v")

        # the timestep is min(dx/|u|, dy/|v|)
        xtmp = self.cc_data.grid.dx/max(abs(u), self.SMALL)
        ytmp = self.cc_data.grid.dy/max(abs(v), self.SMALL)

        self.dt = cfl*min(xtmp, ytmp)
    
    def evolve(self):
        """
        Evolve the linear advection equation through one timestep.  We only
        consider the "density" variable in the CellCenterData2d object that
        is part of the Simulation.
        """

        dtdx = self.dt/self.cc_data.grid.dx
        dtdy = self.dt/self.cc_data.grid.dy

        flux_x, flux_y = flx.unsplit_fluxes(self.cc_data, self.rp, self.dt, "density")

        """
        do the differencing for the fluxes now.  Here, we use slices so we
        avoid slow loops in python.  This is equivalent to:

        myPatch.data[i,j] = myPatch.data[i,j] + \
                               dtdx*(flux_x[i,j] - flux_x[i+1,j]) + \
                               dtdy*(flux_y[i,j] - flux_y[i,j+1])
        """

        dens = self.cc_data.get_var("density")

        dens.v()[:, :] = dens.v() + dtdx*(flux_x.v() - flux_x.ip(1)) + \
                                    dtdy*(flux_y.v() - flux_y.jp(1))

        if self.particles is not None:
            myg = self.cc_data.grid
            u = self.rp.get_param("advection.u")
            v = self.rp.get_param("advection.v")

            u2d = myg.scratch_array() + u
            v2d = myg.scratch_array() + v

            self.particles.update_particles(self.dt, u2d, v2d)
  # increment the time
        self.cc_data.t += self.dt
        self.n += 1


    def dovis(self):
        """
        Do runtime visualization.
        """
        

        dens = self.cc_data.get_var("density")

        myg = self.cc_data.grid

        _, axes, cbar_title = plot_tools.setup_axes(myg, 1)

        # plot density
        
        img = dens
        p = figure()    
        pal = Viridis256
        p.image(image=[img], x=0, y=0,dw = 10, dh = 10, palette=pal)

        show(p)

import mpld3


class TrajectoryView(mpld3.plugins.PluginBase):
    """
    Make it possible to visualize the currently selected trajectory using two lines:
    - trajectory_line works in the background to visualize the entire trajectory
    - selected_line works in the foreground to visualize the selected part of the trajectory in bold

    This plugin creates a bridge element and assumes the figure contains the two lines to be modified,
    since I cannot find a way to dynamically add more lines in an existing figure without re-rending on the server
    everything
    """

    JAVASCRIPT = """
    mpld3.register_plugin("trajectoryview", TrajectoryViewPlugin);
    TrajectoryViewPlugin.prototype = Object.create(mpld3.Plugin.prototype);
    TrajectoryViewPlugin.prototype.constructor = TrajectoryViewPlugin;
    TrajectoryViewPlugin.prototype.requiredProps = ["trajectory_line", "selected_line"];
    TrajectoryViewPlugin.prototype.defaultProps = {}

    function TrajectoryViewPlugin(fig, props){
        mpld3.Plugin.call(this, fig, props);
    };
    
    // This is called at the beginning, and upon refresh?
    TrajectoryViewPlugin.prototype.draw = function(){
        // We need a bridge to capture value change events
        var div = d3.select("#" + this.fig.figid);
        
        // TODO probably we need 4 of them to highlight the selection
        var trajectory_line = mpld3.get_element(this.props.trajectory_line);
        var selected_line = mpld3.get_element(this.props.selected_line);
        
        // Create an hidden input that acts as bridge
        div.append("input")
            .attr("id","the_trajectory")
            .attr("type", "hidden")
        
        var trajectory_placeholder = document.getElementById("the_trajectory");
        
        trajectory_placeholder.addEventListener("UpdateTrajectoryEvent", function(evt) {
                trajectory_line.data = evt.detail.trajectory
                
                if( evt.detail.horizon > 0 ){
					selected_line.data = trajectory_line.data.slice(0, evt.detail.horizon)
				} else {
					selected_line.data = trajectory_line.data
				}
                
                // Show the underlying line
                trajectory_line.elements()
                    .attr("d", trajectory_line.datafunc(trajectory_line.data));
                // Show the bolded line
                selected_line.elements()
                    .attr("d", selected_line.datafunc(selected_line.data));
                    
          });       
    };
    """

    def __init__(self, trajectory_line, selected_line):
        self.dict_ = {
            "type": "trajectoryview",
            "trajectory_line": mpld3.utils.get_id(trajectory_line),
            "selected_line": mpld3.utils.get_id(selected_line),
        }


class AllTrajectoriesView(mpld3.plugins.PluginBase):
    """
    Make it possible to visualize a bundle of trajectories identified by trajectory_ids
    This plugin assumes that the figure ALREADY contains a number of line-placeholders used to visualize the actual trajectories
    This value is controlled by model.mixed_traffic_scenario.VISIBLE_TRAJECTORIES
    """

    JAVASCRIPT = """
    mpld3.register_plugin("alltrajectoryview", AllTrajectoriesViewPlugin);
    AllTrajectoriesViewPlugin.prototype = Object.create(mpld3.Plugin.prototype);
    AllTrajectoriesViewPlugin.prototype.constructor = AllTrajectoriesViewPlugin;
    AllTrajectoriesViewPlugin.prototype.requiredProps = ["trajectory_ids"];
    AllTrajectoriesViewPlugin.prototype.defaultProps = {alpha_show: 0.2}

    function AllTrajectoriesViewPlugin(fig, props){
        mpld3.Plugin.call(this, fig, props);
    };

    // This is called at the beginning and must setup all the functions
    AllTrajectoriesViewPlugin.prototype.draw = function(){
        // We need a bridge to capture refresh events to refresh the visualization
        var div = d3.select("#" + this.fig.figid);
        div.append("input")
            .attr("id","visible_trajectories_bridge")
            .attr("type", "hidden");

        // Get an handle on the visible trajectories lines and extend them by adding methods
        var reset_me = function() {
			this.elements().attr("d", this.datafunc({}));
        };
            
        var update_me = function(trajectory_data){
			this.elements().attr("d", this.datafunc(trajectory_data));
        };
        
        // Prepare a variable to hold the ref of all the line/trajectories
        var the_visible_trajectories = []
        for(var i=0; i<this.props.trajectory_ids.length; i++){
            
            var obj = mpld3.get_element(this.props.trajectory_ids[i], this.fig);

            // Register the new functions            
            obj.reset_me = reset_me;
            // obj.show_me = show_me
            obj.update_me = update_me;
            
            // Store the object in the list
            the_visible_trajectories.push(obj);
        };
        
        // Register an Event Listener to trigger the refresh of all trajectories
        var visible_trajectories_bridge_placeholder = document.getElementById("visible_trajectories_bridge");
        
        visible_trajectories_bridge_placeholder.addEventListener("Refresh", function(evt) {
                // We assume that the trajectories to visualize are defined inside new_visible_trajectories as LIST
                // The order does not matter 
				var new_visible_trajectories = evt.detail.new_visible_trajectories

                // First we make ALL possible visible trajectories not visible anymore
                the_visible_trajectories.forEach(function(e){ e.reset_me(); });

                // Next we make SOME of the visible trajectories visible. Skip the ones that are empty!
                var visualized = 0
                for(var i=0; i <  new_visible_trajectories.length; i++){
                    // Visualize ONLY the one that exist and only if we have enough placeholders
                    if (JSON.stringify(new_visible_trajectories[i]).length - 2 > 0 &&  visualized < the_visible_trajectories.length){
                        the_visible_trajectories[visualized].update_me(new_visible_trajectories[i])
                        visualized = visualized + 1
                    }              
                }
          });         
    };
    """

    def __init__(self, trajectory_ids):
        self.dict_ = {
            "type": "alltrajectoryview",
            "trajectory_ids": [mpld3.utils.get_id(trajectory_id) for trajectory_id in trajectory_ids]
        }


class ZoomEgoCarPlugin(mpld3.plugins.PluginBase):
    """
    Large maps might show the ego car as a very small rectangle. This plugin automatically center the diagram
    on the ego-car and ensure to focus on it by zooming 10, 20, 30 meters around the Ego Car.
    """
    JAVASCRIPT = """
    // little car icon
    var my_icon = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAACXBIWXMAAAsTAAALEwEAmpwYAAACoklEQVRoge2Yu2sVQRTGJ1hEi0RExYBBRNDCRiSV8cEWCRrEBwm3TqFYGKONj3/AGAtfjZALQawSgqJFwEejhVqEJESx0ULQJgSEaOIjRTT6HfYszI4z+7gzy11hPvhBWM75zndy9959COHl5eX1v6kBdIHLoOoI8jrE3oVqP3gD/hTEaxAUFZ7+6z8LDB+xDI67Dt8KFpVBr8CwsD99htlL9l4Am10ucF0yp0+hy6U567CIf8LXXBmvAnOS8YArY40GpDlzPNtaByXTFbDVhalBW3hGNK/TheldyfCFC8MUvZTm3bE1Ww2+SoanbQ0zqE/Ev8xrbMx6RPznbZNtugzayLOiud02Zvclo0fW0bLrsTT3Xq0mzWBJMrphqFsLdoA20A46wDFQASeYCh/r4Bqq3c69Ot2S5i5xltzqlUyIRV7iNhgHb0V4jtpeeRfYa5y9b4JvSk1vLQs8dRDOFU/yhj8DfpUgeARl6csa/lQJAps4mRa+BfwoQVAT30XKT/mlEoRM40LSAg81De9E+NPXJMIL2xdNDR3bI7I9UTVwrXyFl326edZe8F5T8yDJfELT0K7UnNXUjGQIrmpU49Ov1OzT1EwkmU5pGpqUmkBT8xGszxF+A/ik8QmUumZNzVTeBXqUmquaGoIudNPskcS0+PfpLuKKMqviYgE6L+m0CcCgiN9ouWaZl6BZ54T+e5J7gbLhF6g3foF6U9MCn8EM+ABmwbyIvz2wZYU9Z3nGDM90tkA1oacRrGPoZnAbs1OET15t/Hd0vEWqb0zwrdaywKShaSipqSANGbJMJjWNGZrOF5nUoIuGLKNJTQH4rTTQuen0RWtG0Qtl9c6Xsh1Iazwqwi8R3a88A7uKy5iq3eA5Z6FMR+qYxcvLy8urhPoLf+IiiROBpr0AAAAASUVORK5CYII=";

    // create the plugin
    mpld3.register_plugin("zoomEgoCar", ZoomEgoCarPlugin);
    ZoomEgoCarPlugin.prototype = Object.create(mpld3.Plugin.prototype);
    ZoomEgoCarPlugin.prototype.constructor = ZoomEgoCarPlugin;
    // The actual center of the ego vehicle
    ZoomEgoCarPlugin.prototype.requiredProps = ["vehiclePositionX", "vehiclePositionY"];
    // Zoom Levels. It will reset to the initial one before restarting.
    ZoomEgoCarPlugin.prototype.defaultProps = { zoomLevels: [20, 30, 50] };
    // Store the current zoom level
    ZoomEgoCarPlugin.prototype.currentLevel = 0;
    
    // Extend the figure axes to include this additional method, because I have no idea how to create a selection object 
    // TODO Move this code inside our plugin and just call doZoom on the axes instead
    mpld3_Axes.prototype.doEgoZoom = function(x_min, y_min, x_max, y_max) {
        // Transfom coordinates into pixel position
        sel_x_min = this.x(x_min)
        sel_y_min = this.y(y_min)
        sel_x_max = this.x(x_max)
        sel_y_max = this.y(y_max)
        // Code copied from the BoxZoomPlugin d -> new width and height of the figure to define a scaling factor
        var dx = sel_x_max - sel_x_min;
        var dy = sel_y_max - sel_y_min;
        // Position of the "new" center -> we need this to translate the content in the right position
        var cx = (sel_x_min + sel_x_max) / 2;
        var cy = (sel_y_min + sel_y_max) / 2;
        //
        var scale = dx > dy ? this.width / dx : this.height / dy;
        var transX = this.width / 2 - scale * cx;
        var transY = this.height / 2 - scale * cy;
        // This is how we can create the functional composition of transformation        
        var transform = d3.zoomIdentity.translate(transX, transY).scale(scale);
        // Apply the transformation
        this.doZoom(true, transform, 750);
    };

    ZoomEgoCarPlugin.prototype.cycleZoom = function(fig){       
        // Make sure we call this at leat once
        fig.axes[0].reset()
        if(this.currentLevel >= this.defaultProps.zoomLevels.length){
            fig.axes[0].reset()
            this.currentLevel = 0
        } else {
            let minX = parseFloat(this.props.vehiclePositionX) - parseFloat(this.defaultProps.zoomLevels[this.currentLevel])
            let maxX = parseFloat(this.props.vehiclePositionX) + parseFloat(this.defaultProps.zoomLevels[this.currentLevel])
    		let minY = parseFloat(this.props.vehiclePositionY) - parseFloat(this.defaultProps.zoomLevels[this.currentLevel])
	    	let maxY = parseFloat(this.props.vehiclePositionY) + parseFloat(this.defaultProps.zoomLevels[this.currentLevel])
			fig.axes[0].doEgoZoom(minX, minY, maxX, maxY)
			this.currentLevel = this.currentLevel + 1
		}		
    }
    
    function ZoomEgoCarPlugin(fig, props){
        mpld3.Plugin.call(this, fig, props);
        // Pass this to the ButtonFactory, we need a reference to "this-as-the-plugin"
        var thePlugin = this              
        // create EgoCar button
        var EgoCarButton = mpld3.ButtonFactory({
            buttonID: "egoCar",
            sticky: false,
            onActivate: function(){thePlugin.cycleZoom(fig);}.bind(this),
            icon: function(){return my_icon;},
        });
        this.fig.buttons.push(EgoCarButton);
    };
    """

    def __init__(self, ego_vehicle_position_x, ego_vehicle_position_y):
        self.dict_ = {
            "type": "zoomEgoCar",
            "vehiclePositionX": ego_vehicle_position_x,
            "vehiclePositionY": ego_vehicle_position_y}
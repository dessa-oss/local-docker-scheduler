# Overview of the plugin system

* Plugins are implemented as subpackages in this `tracker_client_plugins` package.  
* They must derive from the abstract base class in `tracker_client_plugins.TrackerClientBase`.  
* The class must be named the same as the name of the package but in CamelCase.  
* The __init__ of the class will be fed `*args` and `**kwargs` as read from the configuration file in the root project folder.  

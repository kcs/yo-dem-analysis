import matplotlib.pyplot as plt

layer = iface.activeLayer()

def dem_prom(f):
    if f['Crosscorrect prom']:
        return f['Crosscorrect prom']
    if f['Detected prom']:
        return f['Detected prom']
    if f['DEM prom']:
        return f['DEM prom']
    return -32767
    
prom, err = zip(*[(f['Prominence'], dem_prom(f) - f['Prominence']) for f in layer.getFeatures()])
plt.scatter(prom, err)
plt.show()
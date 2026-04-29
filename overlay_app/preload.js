const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronBridge', {
  mouseEnter:   () => ipcRenderer.send('mouse-enter'),
  mouseLeave:   () => ipcRenderer.send('mouse-leave'),
  minimize:     () => ipcRenderer.send('minimize'),
  close:        () => ipcRenderer.send('close-overlay'),
  setOverlaySize: (width, height) => ipcRenderer.send('set-overlay-size', { width, height }),
  dragStart:    () => ipcRenderer.send('drag-start'),
  dragMove:     () => ipcRenderer.send('drag-move'),
  dragEnd:      () => ipcRenderer.send('drag-end'),
  showAugment:  (stage) => ipcRenderer.send('show-augment', stage),
  hideAugment:  () => ipcRenderer.send('hide-augment'),
  showForge:    () => ipcRenderer.send('show-forge'),
  hideForge:    () => ipcRenderer.send('hide-forge'),
  showGods:     (stage) => ipcRenderer.send('show-gods', stage),
  hideGods:     () => ipcRenderer.send('hide-gods'),
  showGodBoon:  () => ipcRenderer.send('show-god-boon'),
  hideGodBoon:  () => ipcRenderer.send('hide-god-boon'),
});

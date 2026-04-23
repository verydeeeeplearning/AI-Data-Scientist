import { getMainWindow } from '../window';

const DEEP_LINK_CHANNEL = 'ds-agent:deep-link';

export function emitDeepLinkToRenderer(rawUri: string): void {
  const win = getMainWindow();
  if (!win) {
    return;
  }
  win.webContents.send(DEEP_LINK_CHANNEL, rawUri);
}

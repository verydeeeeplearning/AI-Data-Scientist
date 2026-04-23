import type { AreaId } from './area';

export interface DeepLinkResource {
  type: string;
  id: string;
}

export interface DeepLink {
  areaId: AreaId;
  path: string;
  resource?: DeepLinkResource;
}

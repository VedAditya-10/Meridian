export interface Store {
  id: string;
  name: string;
  cameras: number;
  location?: string;
  address?: string;
  phone?: string;
  timezone?: string;
  max_cameras?: number;
}

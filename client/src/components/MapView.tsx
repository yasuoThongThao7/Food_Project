import { useEffect } from 'react';
import L from 'leaflet';
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

export interface MapMarker {
  lat: number;
  lng: number;
  label: string;
  order?: number;
  address?: string;
}

interface MapViewProps {
  markers: MapMarker[];
  polyline?: boolean;
}

function markerIcon(order?: number) {
  return new L.DivIcon({
    className: 'food-map-marker',
    html: order ? `<span>${order}</span>` : '<span>•</span>',
    iconSize: [36, 36],
    iconAnchor: [18, 18]
  });
}

function FitMarkers({ markers }: { markers: MapMarker[] }) {
  const map = useMap();
  useEffect(() => {
    if (markers.length === 1) map.setView([markers[0].lat, markers[0].lng], 15);
    if (markers.length > 1) {
      const bounds = L.latLngBounds(markers.map(({ lat, lng }) => [lat, lng]));
      map.fitBounds(bounds, { padding: [32, 32] });
    }
  }, [map, markers]);
  return null;
}

export function MapView({ markers, polyline = false }: MapViewProps) {
  const points = markers.map(({ lat, lng }) => [lat, lng] as [number, number]);
  return (
    <div className="map-frame" aria-label="Bản đồ OpenStreetMap">
      <MapContainer
        key={points.map(([lat, lng]) => `${lat},${lng}`).join('|') || 'empty'}
        center={points[0] ?? [16.0544, 108.2022]}
        zoom={points.length === 1 ? 15 : 12}
        scrollWheelZoom={false}
      >
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <FitMarkers markers={markers} />
        {markers.map((marker, index) => (
          <Marker key={`${marker.lat}-${marker.lng}-${index}`} position={[marker.lat, marker.lng]} icon={markerIcon(marker.order)}>
            <Popup><strong>{marker.order ? `${marker.order}. ` : ''}{marker.label}</strong>{marker.address && <div>{marker.address}</div>}</Popup>
          </Marker>
        ))}
        {polyline && points.length > 1 && <Polyline positions={points} pathOptions={{ color: '#e65f32', weight: 3, dashArray: '8 8' }} />}
      </MapContainer>
    </div>
  );
}

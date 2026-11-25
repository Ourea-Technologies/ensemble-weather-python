"""Current conditions and active alerts for a named location."""

from ensemble_weather import Client

with Client() as client:
    current = client.current("or/mt-hood-meadows")
    alerts = client.alerts("or/mt-hood-meadows")

if current.now is None:
    print("No current conditions are served right now.")
else:
    c = current.now
    print(f"{current.location.name} at {c.time:%H:%M} UTC: {c.text}, {c.temperature} °C")
    print(f"wind {c.wind_speed} m/s from {c.wind_direction}°, source: {c.source}")

print(f"{alerts.count} active alert(s)")
for alert in alerts.items:
    print(f"- {alert.event} ({alert.severity}, {alert.certainty}): {alert.headline}")

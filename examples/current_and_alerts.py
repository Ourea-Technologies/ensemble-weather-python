"""Current conditions and active alerts for a named location."""

from ensemble_weather import Client

with Client() as client:
    now = client.current("or/mt-hood-meadows")
    alerts = client.alerts("or/mt-hood-meadows")

if now.current is None:
    print("No current conditions are served right now.")
else:
    c = now.current
    print(f"{now.location.name} at {c.time:%H:%M} UTC: {c.condition_text}, {c.temperature} °C")
    print(f"wind {c.wind_speed} m/s from {c.wind_direction}°, source: {c.source}")

print(f"{alerts.alert_count} active alert(s)")
for alert in alerts.alerts:
    print(f"- {alert.event} ({alert.severity}, {alert.certainty}): {alert.headline}")

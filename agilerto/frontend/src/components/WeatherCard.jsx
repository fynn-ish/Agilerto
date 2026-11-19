import { dayLabel, round } from '../time'
import Freshness from './Freshness'

export default function WeatherCard({ weather, source, nowMs }) {
  return (
    <article className="rounded-md border border-line bg-white p-4">
      <h3 className="text-lg font-bold">Weather</h3>

      {!weather ? (
        <p className="pt-2">
          {source?.has_data
            ? 'No weather is saved for this location. Weather is stored for the monitored cities. Choose a city from the list.'
            : 'No weather has been downloaded yet. Connect to the internet once, then tap Refresh.'}
        </p>
      ) : (
        <>
          <p className="text-sm text-muted">
            {weather.area}{weather.distance_km >= 1 && <>, {weather.distance_km} km from you</>}
          </p>
          <p className="flex items-baseline gap-3 pt-1">
            <span className="text-4xl font-bold tabular-nums">{round(weather.current.temp_c)}°C</span>
            <span className="text-lg">{weather.current.condition}</span>
          </p>
          <p className="text-sm text-muted">Feels like {round(weather.current.feels_like_c)}°C</p>

          <dl className="grid grid-cols-3 gap-2 pt-3 text-sm">
            <div><dt className="text-muted">Rain now</dt><dd className="font-bold tabular-nums">{round(weather.current.rain_mm, 1)} mm</dd></div>
            <div><dt className="text-muted">Wind</dt><dd className="font-bold tabular-nums">{round(weather.current.wind_kph)} km/h</dd></div>
            <div><dt className="text-muted">Humidity</dt><dd className="font-bold tabular-nums">{round(weather.current.humidity_pct)}%</dd></div>
          </dl>

          <ul className="mt-3 divide-y divide-line border-t border-line">
            {weather.daily.map((d, i) => (
              <li key={d.date} className="py-2 text-sm">
                <p><strong>{dayLabel(d.date, i)}</strong>, {d.condition}</p>
                <p className="text-muted tabular-nums">
                  {round(d.temp_min_c)} to {round(d.temp_max_c)}°C · rain chance {round(d.rain_chance_pct)}% · {round(d.rain_sum_mm, 1)} mm
                </p>
              </li>
            ))}
          </ul>

          <Freshness fetchedAt={weather.fetched_at} stale={weather.stale} nowMs={nowMs} what="weather" />
          <p className="pt-1 text-xs text-muted">
            Forecast model data from Open-Meteo. It is not a PAGASA warning. Check PAGASA for official advisories.
          </p>
        </>
      )}
    </article>
  )
}

const d3 = window.d3;

const state = {
  rows: [],
  boundaries: null,
  borough: "Hillingdon",
  month: "2025-06",
  group: "Fire",
};

const els = {
  borough: document.querySelector("#borough-select"),
  month: document.querySelector("#month-select"),
  group: document.querySelector("#group-select"),
  summary: document.querySelector("#selection-summary"),
  incidents: document.querySelector("#metric-incidents"),
  median: document.querySelector("#metric-median"),
  exceed: document.querySelector("#metric-exceed"),
  map: d3.select("#borough-map"),
  trend: d3.select("#trend-chart"),
  distribution: d3.select("#distribution-chart"),
  tooltip: document.querySelector("#tooltip"),
  legend: document.querySelector("#map-legend"),
  ranking: document.querySelector("#ranking-body"),
  emptyState: document.querySelector("#empty-state"),
};

function normName(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function fmtInt(value) {
  return d3.format(",")(Math.round(value || 0));
}

function fmtMin(value) {
  return value == null || Number.isNaN(value) ? "-" : d3.format(".1f")(value);
}

function fmtPct(value) {
  return value == null || Number.isNaN(value) ? "-" : d3.format(".0%")(value);
}

function selectedRows() {
  return state.rows.filter(
    (row) => row.year_month === state.month && row.IncidentGroup === state.group,
  );
}

function selectedBoroughRows() {
  return state.rows.filter(
    (row) =>
      row.borough_canonical === state.borough && row.IncidentGroup === state.group,
  );
}

function rowForSelection() {
  return state.rows.find(
    (row) =>
      row.borough_canonical === state.borough &&
      row.year_month === state.month &&
      row.IncidentGroup === state.group,
  );
}

function populateControls() {
  const boroughs = Array.from(new Set(state.rows.map((d) => d.borough_canonical))).sort();
  const months = Array.from(new Set(state.rows.map((d) => d.year_month))).sort();
  const groups = Array.from(new Set(state.rows.map((d) => d.IncidentGroup))).sort();

  fillSelect(els.borough, boroughs, state.borough);
  fillSelect(els.month, months, state.month);
  fillSelect(els.group, groups, state.group);

  els.borough.addEventListener("change", () => {
    state.borough = els.borough.value;
    render();
  });
  els.month.addEventListener("change", () => {
    state.month = els.month.value;
    render();
  });
  els.group.addEventListener("change", () => {
    state.group = els.group.value;
    render();
  });
}

function fillSelect(select, values, selected) {
  select.replaceChildren(
    ...values.map((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      option.selected = value === selected;
      return option;
    }),
  );
}

function renderSummary() {
  const row = rowForSelection();
  els.summary.textContent = `${state.borough} · ${state.month} · ${state.group}`;
  els.incidents.textContent = row ? fmtInt(row.incident_count) : "-";
  els.median.textContent = row ? fmtMin(row.response_time_min_median) : "-";
  els.exceed.textContent = row ? fmtPct(row.exceeds_six_min_share) : "-";
  if (els.emptyState) {
    els.emptyState.hidden = row != null;
  }
}

function renderMap() {
  const width = els.map.node().clientWidth || 720;
  const height = els.map.node().clientHeight || 520;
  const rowsByBorough = new Map(selectedRows().map((row) => [normName(row.borough_canonical), row]));
  const values = Array.from(rowsByBorough.values())
    .map((row) => row.exceeds_six_min_share)
    .filter((value) => value != null && !Number.isNaN(value));
  const color = d3
    .scaleSequential()
    .domain(d3.extent(values))
    .interpolator(
      d3.interpolateRgbBasis(["#d9efed", "#78c9c7", "#087f8c", "#f0a13a", "#c43d35"]),
    );

  els.map.selectAll("*").remove();
  els.map.attr("viewBox", `0 0 ${width} ${height}`);

  const projection = d3.geoIdentity().reflectY(true).fitSize([width, height], state.boundaries);
  const path = d3.geoPath(projection);

  els.map
    .append("g")
    .selectAll("path")
    .data(state.boundaries.features)
    .join("path")
    .attr("class", (feature) =>
      normName(feature.properties.name) === normName(state.borough)
        ? "borough selected"
        : "borough",
    )
    .attr("d", path)
    .attr("fill", (feature) => {
      const row = rowsByBorough.get(normName(feature.properties.name));
      return row?.exceeds_six_min_share == null ? "#eef2ef" : color(row.exceeds_six_min_share);
    })
    .attr("opacity", (feature) => {
      const row = rowsByBorough.get(normName(feature.properties.name));
      return row ? 1 : 0.45;
    })
    .on("click", (_, feature) => {
      const match = state.rows.find(
        (row) => normName(row.borough_canonical) === normName(feature.properties.name),
      );
      if (match) {
        state.borough = match.borough_canonical;
        els.borough.value = state.borough;
        render();
      }
    })
    .on("mousemove", (event, feature) => {
      const row = rowsByBorough.get(normName(feature.properties.name));
      showTooltip(event, feature.properties.name, row);
    })
    .on("mouseleave", hideTooltip);

  const [min, max] = d3.extent(values);
  els.legend.innerHTML = `
    <span>${fmtPct(min)}</span>
    <span class="legend-swatch" aria-hidden="true"></span>
    <span>${fmtPct(max)}</span>
    <span>share over six minutes</span>
  `;
}

function showTooltip(event, name, row) {
  els.tooltip.hidden = false;
  els.tooltip.innerHTML = row
    ? `<strong>${name}</strong>
       ${fmtInt(row.incident_count)} incidents<br>
       Median ${fmtMin(row.response_time_min_median)} min · P90 ${fmtMin(row.response_time_min_p90)} min<br>
       ${fmtPct(row.exceeds_six_min_share)} over six minutes among recorded first-pump times<br>
       ${fmtPct(row.coord_precise_share)} precise-coordinate coverage`
    : `<strong>${name}</strong>No selected-cell incidents`;
  const rect = event.currentTarget.ownerSVGElement.getBoundingClientRect();
  els.tooltip.style.left = `${event.clientX - rect.left + 14}px`;
  els.tooltip.style.top = `${event.clientY - rect.top + 14}px`;
}

function hideTooltip() {
  els.tooltip.hidden = true;
}

function renderTrend() {
  const data = selectedBoroughRows().sort((a, b) => d3.ascending(a.year_month, b.year_month));
  const width = els.trend.node().clientWidth || 420;
  const height = els.trend.node().clientHeight || 250;
  const margin = { top: 22, right: 34, bottom: 34, left: 48 };

  els.trend.selectAll("*").remove();
  els.trend.attr("viewBox", `0 0 ${width} ${height}`);

  const x = d3
    .scalePoint()
    .domain(data.map((d) => d.year_month))
    .range([margin.left, width - margin.right])
    .padding(0.35);
  const y = d3
    .scaleLinear()
    .domain([0, d3.max(data, (d) => d.incident_count) || 1])
    .nice()
    .range([height - margin.bottom, margin.top]);
  const y2 = d3.scaleLinear().domain([0, 1]).range([height - margin.bottom, margin.top]);

  els.trend
    .append("g")
    .attr("class", "grid")
    .attr("transform", `translate(${margin.left},0)`)
    .call(d3.axisLeft(y).ticks(5).tickSize(-(width - margin.left - margin.right)).tickFormat(""))
    .call((g) => g.select(".domain").remove());

  els.trend
    .append("path")
    .datum(data)
    .attr("class", "line-incidents")
    .attr(
      "d",
      d3
        .line()
        .defined((d) => d.incident_count != null)
        .x((d) => x(d.year_month))
        .y((d) => y(d.incident_count)),
    );

  els.trend
    .append("path")
    .datum(data)
    .attr("class", "line-exceed")
    .attr(
      "d",
      d3
        .line()
        .defined((d) => d.exceeds_six_min_share != null)
        .x((d) => x(d.year_month))
        .y((d) => y2(d.exceeds_six_min_share)),
    );

  els.trend
    .append("g")
    .attr("class", "axis")
    .attr("transform", `translate(0,${height - margin.bottom})`)
    .call(
      d3
        .axisBottom(x)
        .tickValues(x.domain().filter((_, i) => i % (width < 520 ? 8 : 4) === 0)),
    )
    .call((g) => g.select(".domain").remove());

  els.trend
    .append("g")
    .attr("class", "axis")
    .attr("transform", `translate(${margin.left},0)`)
    .call(d3.axisLeft(y).ticks(5))
    .call((g) => g.select(".domain").remove());

  els.trend
    .append("text")
    .attr("class", "chart-label")
    .attr("x", margin.left)
    .attr("y", 12)
    .text("Incidents");

  els.trend
    .append("text")
    .attr("class", "chart-label")
    .attr("x", width - margin.right - 92)
    .attr("y", 12)
    .attr("fill", "var(--amber)")
    .text("Over 6 min");
}

function renderDistribution() {
  const data = state.rows
    .filter((row) => row.borough_canonical === state.borough && row.year_month === state.month)
    .sort((a, b) => d3.ascending(a.IncidentGroup, b.IncidentGroup));
  const width = els.distribution.node().clientWidth || 420;
  const height = els.distribution.node().clientHeight || 250;
  const margin = { top: 26, right: 24, bottom: 34, left: 116 };

  els.distribution.selectAll("*").remove();
  els.distribution.attr("viewBox", `0 0 ${width} ${height}`);

  const x = d3
    .scaleLinear()
    .domain([0, d3.max(data, (d) => d.response_time_min_p95) || 10])
    .nice()
    .range([margin.left, width - margin.right]);
  const y = d3
    .scaleBand()
    .domain(data.map((d) => d.IncidentGroup))
    .range([margin.top, height - margin.bottom])
    .padding(0.42);

  els.distribution
    .append("g")
    .attr("class", "axis")
    .attr("transform", `translate(0,${height - margin.bottom})`)
    .call(d3.axisBottom(x).ticks(5))
    .call((g) => g.select(".domain").remove());

  els.distribution
    .append("g")
    .attr("class", "axis")
    .attr("transform", `translate(${margin.left},0)`)
    .call(d3.axisLeft(y).tickSize(0))
    .call((g) => g.select(".domain").remove());

  const group = els.distribution.append("g");

  group
    .selectAll("line.range")
    .data(data)
    .join("line")
    .attr("x1", (d) => x(d.response_time_min_median))
    .attr("x2", (d) => x(d.response_time_min_p95))
    .attr("y1", (d) => y(d.IncidentGroup) + y.bandwidth() / 2)
    .attr("y2", (d) => y(d.IncidentGroup) + y.bandwidth() / 2)
    .attr("stroke", "#9fb5ae")
    .attr("stroke-width", 8)
    .attr("stroke-linecap", "round");

  group
    .selectAll("circle.median")
    .data(data)
    .join("circle")
    .attr("cx", (d) => x(d.response_time_min_median))
    .attr("cy", (d) => y(d.IncidentGroup) + y.bandwidth() / 2)
    .attr("r", 5)
    .attr("fill", (d) => (d.IncidentGroup === state.group ? "var(--teal-dark)" : "#4d6961"));

  group
    .append("line")
    .attr("x1", x(6))
    .attr("x2", x(6))
    .attr("y1", margin.top - 8)
    .attr("y2", height - margin.bottom)
    .attr("stroke", "var(--amber)")
    .attr("stroke-width", 1.5)
    .attr("stroke-dasharray", "4 4");

  group
    .append("text")
    .attr("class", "chart-label")
    .attr("x", x(6) + 6)
    .attr("y", margin.top - 11)
    .text("6 min");
}

function renderTable() {
  const rows = selectedRows()
    .slice()
    .sort((a, b) => d3.descending(a.exceeds_six_min_share, b.exceeds_six_min_share));

  els.ranking.replaceChildren(
    ...rows.map((row) => {
      const tr = document.createElement("tr");
      tr.className = row.borough_canonical === state.borough ? "selected-row" : "";
      tr.innerHTML = `
        <td>${row.borough_canonical}</td>
        <td>${fmtInt(row.incident_count)}</td>
        <td>${fmtMin(row.response_time_min_median)} min</td>
        <td>${fmtMin(row.response_time_min_p90)} min</td>
        <td>${fmtPct(row.exceeds_six_min_share)}</td>
        <td>${fmtPct(row.coord_precise_share)}</td>
      `;
      tr.addEventListener("click", () => {
        state.borough = row.borough_canonical;
        els.borough.value = state.borough;
        render();
      });
      return tr;
    }),
  );
}

function render() {
  renderSummary();
  renderMap();
  renderTrend();
  renderDistribution();
  renderTable();
}

async function init() {
  const [summaryResponse, boundaryResponse] = await Promise.all([
    fetch("/api/borough_summary"),
    fetch("/api/borough_boundaries"),
  ]);
  if (!summaryResponse.ok || !boundaryResponse.ok) {
    throw new Error("Dashboard data request failed");
  }
  const summaryPayload = await summaryResponse.json();
  state.rows = summaryPayload.rows;
  state.boundaries = await boundaryResponse.json();
  populateControls();
  render();
}

window.addEventListener("resize", () => render());

init().catch((error) => {
  document.body.innerHTML = `<main class="load-error"><h1>Dashboard failed to load</h1><p>${error.message}</p></main>`;
});

import { useEffect, useMemo, useRef, useState } from "react";

import type { EventLabel, SelectionRange, SessionSample, ViewRange } from "./types";

type TimelineProps = {
  samples: SessionSample[];
  labels: EventLabel[];
  isSelectionMode: boolean;
  selectedRange: SelectionRange | null;
  focusRange: ViewRange | null;
  selectedLabelId: number | null;
  onRangeSelected: (range: SelectionRange) => void;
  onSelectedRangeChange: (range: SelectionRange) => void;
};

type Lane = {
  id: string;
  title: string;
  unit: string;
  series: Array<{
    key: keyof SessionSample;
    label: string;
    color: string;
  }>;
};

const LANES: Lane[] = [
  {
    id: "accel",
    title: "Acceleration",
    unit: "g",
    series: [
      { key: "ax", label: "ax", color: "#c6552b" },
      { key: "ay", label: "ay", color: "#2d7a6f" },
      { key: "az", label: "az", color: "#375a9e" },
    ],
  },
  {
    id: "gyro",
    title: "Gyroscope",
    unit: "deg/s",
    series: [
      { key: "gx", label: "gx", color: "#c6552b" },
      { key: "gy", label: "gy", color: "#2d7a6f" },
      { key: "gz", label: "gz", color: "#375a9e" },
    ],
  },
  {
    id: "accel-mag",
    title: "Accel Magnitude",
    unit: "g",
    series: [{ key: "accel_mag", label: "|a|", color: "#d8892f" }],
  },
  {
    id: "gyro-mag",
    title: "Gyro Magnitude",
    unit: "deg/s",
    series: [{ key: "gyro_mag", label: "|g|", color: "#4b6f40" }],
  },
];

const WIDTH = 1200;
const LANE_HEIGHT = 132;
const LEFT_PAD = 86;
const RIGHT_PAD = 22;
const TOP_PAD = 20;
const BOTTOM_PAD = 44;
const HEIGHT = TOP_PAD + BOTTOM_PAD + LANES.length * LANE_HEIGHT;
const MIN_SPAN_MS = 1000;

function eventColor(eventType: string): string {
  const colors: Record<string, string> = {
    seizure: "rgba(178, 36, 59, 0.22)",
    sleep_twitch: "rgba(84, 88, 160, 0.2)",
    scratching: "rgba(219, 133, 46, 0.24)",
    scooting: "rgba(152, 92, 43, 0.22)",
    shake_off: "rgba(32, 127, 118, 0.22)",
    walking: "rgba(75, 111, 64, 0.2)",
    running: "rgba(49, 85, 154, 0.2)",
    resting: "rgba(96, 115, 91, 0.17)",
    unknown: "rgba(65, 65, 65, 0.16)",
  };
  return colors[eventType] ?? colors.unknown;
}

function clampRange(start: number, end: number, min: number, max: number): [number, number] {
  const span = end - start;
  if (span >= max - min) {
    return [min, max];
  }
  if (start < min) {
    return [min, min + span];
  }
  if (end > max) {
    return [max - span, max];
  }
  return [start, end];
}

function formatTick(date: Date, spanMs: number): string {
  if (spanMs > 1000 * 60 * 60 * 24) {
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  }
  if (spanMs > 1000 * 60 * 60) {
    return date.toLocaleString([], { month: "short", day: "numeric", hour: "numeric" });
  }
  if (spanMs > 1000 * 60) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function getValue(sample: SessionSample, key: keyof SessionSample): number {
  const value = sample[key];
  return typeof value === "number" ? value : 0;
}

function buildPath(
  samples: SessionSample[],
  key: keyof SessionSample,
  xScale: (deviceMs: number) => number,
  yScale: (value: number) => number,
): string {
  return samples.map((sample) => `${xScale(sample.device_ms).toFixed(2)},${yScale(getValue(sample, key)).toFixed(2)}`).join(" ");
}

function nearestSampleDate(samples: SessionSample[], deviceMs: number): Date {
  if (samples.length === 0) {
    return new Date();
  }
  let nearest = samples[0];
  let nearestDistance = Math.abs(nearest.device_ms - deviceMs);
  for (const sample of samples) {
    const distance = Math.abs(sample.device_ms - deviceMs);
    if (distance < nearestDistance) {
      nearest = sample;
      nearestDistance = distance;
    }
  }
  return new Date(nearest.server_received_at);
}

function Timeline({
  samples,
  labels,
  isSelectionMode,
  onRangeSelected,
  onSelectedRangeChange,
  selectedLabelId,
  selectedRange,
  focusRange,
}: TimelineProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [viewRange, setViewRange] = useState<[number, number] | null>(null);
  const [dragStart, setDragStart] = useState<{ pointerX: number; range: [number, number] } | null>(null);
  const [selectionDrag, setSelectionDrag] = useState<number | null>(null);
  const [handleDrag, setHandleDrag] = useState<"start" | "end" | null>(null);
  const [selectionDraft, setSelectionDraft] = useState<SelectionRange | null>(null);
  const [verticalScale, setVerticalScale] = useState(1);

  const domain = useMemo<[number, number] | null>(() => {
    if (samples.length === 0) {
      return null;
    }
    return [samples[0].device_ms, samples[samples.length - 1].device_ms];
  }, [samples]);

  useEffect(() => {
    setViewRange(domain);
  }, [domain]);

  useEffect(() => {
    if (domain && focusRange) {
      setViewRange(clampRange(focusRange.startDeviceMs, focusRange.endDeviceMs, domain[0], domain[1]));
    }
  }, [domain, focusRange]);

  const currentRange = viewRange ?? domain;
  const visibleSamples = useMemo(() => {
    if (!currentRange) {
      return [];
    }
    const [start, end] = currentRange;
    return samples.filter((sample) => sample.device_ms >= start && sample.device_ms <= end);
  }, [currentRange, samples]);

  if (!domain || !currentRange) {
    return (
      <div className="empty-timeline">
        <strong>No samples loaded.</strong>
        <span>Upload or select a session with IMU samples.</span>
      </div>
    );
  }

  const [domainStart, domainEnd] = domain;
  const activeRange: [number, number] = currentRange;
  const [viewStart, viewEnd] = activeRange;
  const totalSpan = domainEnd - domainStart;
  const viewSpan = viewEnd - viewStart;
  const viewPercent = totalSpan > 0 ? (viewSpan / totalSpan) * 100 : 100;
  const horizontalPercent = totalSpan > viewSpan ? ((viewStart - domainStart) / (totalSpan - viewSpan)) * 100 : 0;
  const plotWidth = WIDTH - LEFT_PAD - RIGHT_PAD;

  function setClampedViewRange(start: number, end: number) {
    setViewRange(clampRange(start, end, domainStart, domainEnd));
  }

  function xScale(deviceMs: number): number {
    return LEFT_PAD + ((deviceMs - viewStart) / viewSpan) * plotWidth;
  }

  function pointerToDeviceMs(clientX: number): number {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) {
      return viewStart;
    }
    const svgX = ((clientX - rect.left) / rect.width) * WIDTH;
    const ratio = Math.min(1, Math.max(0, (svgX - LEFT_PAD) / plotWidth));
    return viewStart + ratio * viewSpan;
  }

  function zoomAround(focus: number, multiplier: number) {
    const nextSpan = Math.min(totalSpan, Math.max(MIN_SPAN_MS, viewSpan * multiplier));
    const focusRatio = (focus - viewStart) / viewSpan;
    const nextStart = focus - nextSpan * focusRatio;
    setClampedViewRange(nextStart, nextStart + nextSpan);
  }

  function panBy(deltaMs: number) {
    setClampedViewRange(viewStart + deltaMs, viewEnd + deltaMs);
  }

  function handleWheel(event: React.WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    if (Math.abs(event.deltaX) > Math.abs(event.deltaY) || event.shiftKey) {
      panBy(event.deltaX * (viewSpan / plotWidth));
      return;
    }
    const focus = pointerToDeviceMs(event.clientX);
    zoomAround(focus, event.deltaY < 0 ? 0.78 : 1.28);
  }

  function handlePointerDown(event: React.PointerEvent<SVGSVGElement>) {
    event.preventDefault();
    svgRef.current?.setPointerCapture(event.pointerId);
    const pointerMs = Math.round(pointerToDeviceMs(event.clientX));
    const handleToleranceMs = viewSpan * 0.012;

    if (selectedRange && Math.abs(pointerMs - selectedRange.startDeviceMs) <= handleToleranceMs) {
      setHandleDrag("start");
      return;
    }
    if (selectedRange && Math.abs(pointerMs - selectedRange.endDeviceMs) <= handleToleranceMs) {
      setHandleDrag("end");
      return;
    }
    if (isSelectionMode) {
      setSelectionDrag(pointerMs);
      setSelectionDraft({ startDeviceMs: pointerMs, endDeviceMs: pointerMs });
      return;
    }
    setDragStart({ pointerX: event.clientX, range: activeRange });
  }

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const currentMs = Math.round(pointerToDeviceMs(event.clientX));
    if (handleDrag && selectedRange) {
      const nextRange =
        handleDrag === "start"
          ? { startDeviceMs: Math.min(currentMs, selectedRange.endDeviceMs - 1), endDeviceMs: selectedRange.endDeviceMs }
          : { startDeviceMs: selectedRange.startDeviceMs, endDeviceMs: Math.max(currentMs, selectedRange.startDeviceMs + 1) };
      onSelectedRangeChange(nextRange);
      return;
    }
    if (selectionDrag !== null) {
      setSelectionDraft({
        startDeviceMs: Math.min(selectionDrag, currentMs),
        endDeviceMs: Math.max(selectionDrag, currentMs),
      });
      return;
    }
    if (!dragStart) {
      return;
    }
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) {
      return;
    }
    const deltaPx = event.clientX - dragStart.pointerX;
    const deltaMs = (deltaPx / rect.width) * WIDTH * ((dragStart.range[1] - dragStart.range[0]) / plotWidth);
    setClampedViewRange(dragStart.range[0] - deltaMs, dragStart.range[1] - deltaMs);
  }

  function handlePointerUp(event: React.PointerEvent<SVGSVGElement>) {
    svgRef.current?.releasePointerCapture(event.pointerId);
    if (selectionDraft && selectionDraft.endDeviceMs > selectionDraft.startDeviceMs) {
      onRangeSelected(selectionDraft);
    }
    setSelectionDrag(null);
    setSelectionDraft(null);
    setHandleDrag(null);
    setDragStart(null);
  }

  const ticks = Array.from({ length: 6 }, (_, index) => viewStart + (viewSpan * index) / 5);
  const visibleSelection = selectionDraft ?? selectedRange;

  return (
    <div className="timeline-card">
      <div className="timeline-toolbar">
        <div>
          <strong>{visibleSamples.length.toLocaleString()}</strong>
          <span> visible points · view {viewPercent.toFixed(1)}%</span>
        </div>
        <div className="zoom-controls" aria-label="Timeline view controls">
          <button type="button" onClick={() => zoomAround((viewStart + viewEnd) / 2, 1.25)}>
            -
          </button>
          <span>{viewPercent.toFixed(1)}%</span>
          <button type="button" onClick={() => zoomAround((viewStart + viewEnd) / 2, 0.8)}>
            +
          </button>
          <button type="button" onClick={() => setViewRange(domain)}>
            Reset
          </button>
        </div>
      </div>

      <div className="timeline-sliders">
        <label>
          Horizontal
          <input
            max={100}
            min={0}
            onChange={(event) => {
              const ratio = Number(event.target.value) / 100;
              const nextStart = domainStart + (totalSpan - viewSpan) * ratio;
              setClampedViewRange(nextStart, nextStart + viewSpan);
            }}
            step={0.1}
            type="range"
            value={horizontalPercent}
          />
        </label>
        <label>
          Vertical scale
          <input
            max={300}
            min={50}
            onChange={(event) => setVerticalScale(Number(event.target.value) / 100)}
            step={5}
            type="range"
            value={verticalScale * 100}
          />
          <span>{Math.round(verticalScale * 100)}%</span>
        </label>
      </div>

      <svg
        aria-label="IMU timeline"
        className="timeline-svg"
        onPointerDown={handlePointerDown}
        onPointerLeave={() => {
          setDragStart(null);
          setSelectionDrag(null);
          setHandleDrag(null);
        }}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onWheel={handleWheel}
        ref={svgRef}
        role="img"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      >
        <rect className="timeline-background" height={HEIGHT} width={WIDTH} x={0} y={0} />
        {labels.map((label) => {
          if (label.end_device_ms < viewStart || label.start_device_ms > viewEnd) {
            return null;
          }
          const x = Math.max(LEFT_PAD, xScale(label.start_device_ms));
          const width = Math.max(2, Math.min(WIDTH - RIGHT_PAD, xScale(label.end_device_ms)) - x);
          return (
            <g key={label.id}>
              <rect
                className={label.id === selectedLabelId ? "label-overlay selected" : "label-overlay"}
                fill={eventColor(label.event_type)}
                height={LANES.length * LANE_HEIGHT}
                rx={8}
                width={width}
                x={x}
                y={TOP_PAD}
              />
              <text className="label-overlay-text" x={x + 7} y={TOP_PAD + 18}>
                {label.event_type}
              </text>
            </g>
          );
        })}

        {visibleSelection && visibleSelection.endDeviceMs >= viewStart && visibleSelection.startDeviceMs <= viewEnd ? (
          <g>
            <rect
              className="selection-overlay"
              height={LANES.length * LANE_HEIGHT}
              rx={10}
              width={Math.max(
                3,
                Math.min(WIDTH - RIGHT_PAD, xScale(visibleSelection.endDeviceMs)) -
                  Math.max(LEFT_PAD, xScale(visibleSelection.startDeviceMs)),
              )}
              x={Math.max(LEFT_PAD, xScale(visibleSelection.startDeviceMs))}
              y={TOP_PAD}
            />
            {(["startDeviceMs", "endDeviceMs"] as const).map((key) => (
              <g className="selection-handle" key={key}>
                <line
                  x1={xScale(visibleSelection[key])}
                  x2={xScale(visibleSelection[key])}
                  y1={TOP_PAD}
                  y2={TOP_PAD + LANES.length * LANE_HEIGHT}
                />
                <circle cx={xScale(visibleSelection[key])} cy={TOP_PAD + 12} r={7} />
              </g>
            ))}
          </g>
        ) : null}

        {LANES.map((lane, laneIndex) => {
          const laneTop = TOP_PAD + laneIndex * LANE_HEIGHT;
          const laneMid = laneTop + LANE_HEIGHT / 2;
          const allValues = visibleSamples.flatMap((sample) => lane.series.map((series) => getValue(sample, series.key)));
          const minValue = Math.min(...allValues);
          const maxValue = Math.max(...allValues);
          const rawPadding = Math.max(0.1, (maxValue - minValue) * 0.12);
          const rawMid = (maxValue + minValue) / 2;
          const rawHalfSpan = Math.max(0.1, (maxValue - minValue) / 2 + rawPadding) / verticalScale;
          const yMin = rawMid - rawHalfSpan;
          const yMax = rawMid + rawHalfSpan;
          const yScale = (value: number) =>
            laneTop + LANE_HEIGHT - 18 - ((value - yMin) / (yMax - yMin || 1)) * (LANE_HEIGHT - 34);

          return (
            <g key={lane.id}>
              <line className="lane-rule" x1={LEFT_PAD} x2={WIDTH - RIGHT_PAD} y1={laneTop + LANE_HEIGHT} y2={laneTop + LANE_HEIGHT} />
              <text className="lane-title" x={18} y={laneMid - 7}>
                {lane.title}
              </text>
              <text className="lane-unit" x={18} y={laneMid + 13}>
                {lane.unit}
              </text>
              {lane.series.map((series) => (
                <polyline
                  fill="none"
                  key={series.key}
                  points={buildPath(visibleSamples, series.key, xScale, yScale)}
                  stroke={series.color}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2.2}
                />
              ))}
            </g>
          );
        })}

        {ticks.map((tick) => (
          <g key={tick}>
            <line className="time-grid" x1={xScale(tick)} x2={xScale(tick)} y1={TOP_PAD} y2={HEIGHT - BOTTOM_PAD} />
            <text className="time-tick" x={xScale(tick)} y={HEIGHT - 14}>
              {formatTick(nearestSampleDate(samples, tick), viewSpan)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

export default Timeline;

import { useEffect, useMemo, useRef, useState } from "react";

import type { EventLabel, SessionSample } from "./types";

type TimelineProps = {
  samples: SessionSample[];
  labels: EventLabel[];
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
const BOTTOM_PAD = 34;
const HEIGHT = TOP_PAD + BOTTOM_PAD + LANES.length * LANE_HEIGHT;

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

function formatMs(ms: number): string {
  const seconds = ms / 1000;
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }
  return `${(seconds / 60).toFixed(2)}m`;
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

function Timeline({ samples, labels }: TimelineProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [viewRange, setViewRange] = useState<[number, number] | null>(null);
  const [dragStart, setDragStart] = useState<{ pointerX: number; range: [number, number] } | null>(null);

  const domain = useMemo<[number, number] | null>(() => {
    if (samples.length === 0) {
      return null;
    }
    return [samples[0].device_ms, samples[samples.length - 1].device_ms];
  }, [samples]);

  useEffect(() => {
    setViewRange(domain);
  }, [domain]);

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

  const activeRange: [number, number] = currentRange;
  const [domainStart, domainEnd] = domain;
  const [viewStart, viewEnd] = activeRange;
  const plotWidth = WIDTH - LEFT_PAD - RIGHT_PAD;

  function xScale(deviceMs: number): number {
    return LEFT_PAD + ((deviceMs - viewStart) / (viewEnd - viewStart)) * plotWidth;
  }

  function pointerToDeviceMs(clientX: number): number {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) {
      return viewStart;
    }
    const svgX = ((clientX - rect.left) / rect.width) * WIDTH;
    const ratio = Math.min(1, Math.max(0, (svgX - LEFT_PAD) / plotWidth));
    return viewStart + ratio * (viewEnd - viewStart);
  }

  function handleWheel(event: React.WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    const focus = pointerToDeviceMs(event.clientX);
    const zoomFactor = event.deltaY < 0 ? 0.78 : 1.28;
    const currentSpan = viewEnd - viewStart;
    const nextSpan = Math.min(domainEnd - domainStart, Math.max(1000, currentSpan * zoomFactor));
    const focusRatio = (focus - viewStart) / currentSpan;
    const nextStart = focus - nextSpan * focusRatio;
    setViewRange(clampRange(nextStart, nextStart + nextSpan, domainStart, domainEnd));
  }

  function handlePointerDown(event: React.PointerEvent<SVGSVGElement>) {
    svgRef.current?.setPointerCapture(event.pointerId);
    setDragStart({ pointerX: event.clientX, range: activeRange });
  }

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    if (!dragStart) {
      return;
    }
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) {
      return;
    }
    const deltaPx = event.clientX - dragStart.pointerX;
    const deltaMs = (deltaPx / rect.width) * WIDTH * ((dragStart.range[1] - dragStart.range[0]) / plotWidth);
    setViewRange(clampRange(dragStart.range[0] - deltaMs, dragStart.range[1] - deltaMs, domainStart, domainEnd));
  }

  function handlePointerUp(event: React.PointerEvent<SVGSVGElement>) {
    svgRef.current?.releasePointerCapture(event.pointerId);
    setDragStart(null);
  }

  const ticks = Array.from({ length: 6 }, (_, index) => viewStart + ((viewEnd - viewStart) * index) / 5);

  return (
    <div className="timeline-card">
      <div className="timeline-toolbar">
        <div>
          <strong>{visibleSamples.length.toLocaleString()}</strong>
          <span> visible points</span>
        </div>
        <button type="button" onClick={() => setViewRange(domain)}>
          Reset zoom
        </button>
      </div>
      <svg
        aria-label="IMU timeline"
        className="timeline-svg"
        onPointerDown={handlePointerDown}
        onPointerLeave={() => setDragStart(null)}
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

        {LANES.map((lane, laneIndex) => {
          const laneTop = TOP_PAD + laneIndex * LANE_HEIGHT;
          const laneMid = laneTop + LANE_HEIGHT / 2;
          const allValues = visibleSamples.flatMap((sample) => lane.series.map((series) => getValue(sample, series.key)));
          const minValue = Math.min(...allValues);
          const maxValue = Math.max(...allValues);
          const padding = Math.max(0.1, (maxValue - minValue) * 0.12);
          const yMin = minValue - padding;
          const yMax = maxValue + padding;
          const yScale = (value: number) => laneTop + LANE_HEIGHT - 18 - ((value - yMin) / (yMax - yMin || 1)) * (LANE_HEIGHT - 34);

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
            <text className="time-tick" x={xScale(tick)} y={HEIGHT - 10}>
              {formatMs(tick - domainStart)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

export default Timeline;

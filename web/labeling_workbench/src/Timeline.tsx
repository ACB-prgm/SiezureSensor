import { useEffect, useMemo, useRef, useState } from "react";

import type { EventLabel, SelectionRange, SessionSample, SessionSampleWindow, ViewRange } from "./types";

type TimelineProps = {
  samples: SessionSample[];
  labels: EventLabel[];
  isSelectionMode: boolean;
  selectedRange: SelectionRange | null;
  focusRange: ViewRange | null;
  selectedLabelId: number | null;
  sampleWindow: SessionSampleWindow | null;
  onRangeSelected: (range: SelectionRange) => void;
  onSelectedRangeChange: (range: SelectionRange) => void;
  onRequestOlderWindow: () => void;
  onRequestNewerWindow: () => void;
  onRequestLatestWindow: () => void;
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
const TOP_PAD = 38;
const BOTTOM_PAD = 44;
const HEIGHT = TOP_PAD + BOTTOM_PAD + LANES.length * LANE_HEIGHT;
const MIN_SPAN_MS = 1000;
const DEFAULT_LIVE_SPAN_MS = 10 * 60 * 1000;

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

function latestRange(domain: [number, number], preferredSpan = DEFAULT_LIVE_SPAN_MS): [number, number] {
  const [domainStart, domainEnd] = domain;
  const totalSpan = domainEnd - domainStart;
  const span = Math.min(totalSpan, Math.max(MIN_SPAN_MS, Math.min(preferredSpan, totalSpan)));
  return [domainEnd - span, domainEnd];
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
  xScale: (timeMs: number) => number,
  yScale: (value: number) => number,
): string {
  return samples.map((sample) => `${xScale(sampleTimeMs(sample)).toFixed(2)},${yScale(getValue(sample, key)).toFixed(2)}`).join(" ");
}

function sampleTimeMs(sample: SessionSample): number {
  return new Date(sample.server_received_at).getTime();
}

function nearestSampleByTime(samples: SessionSample[], timeMs: number): SessionSample | null {
  if (samples.length === 0) {
    return null;
  }
  let nearest = samples[0];
  let nearestDistance = Math.abs(sampleTimeMs(nearest) - timeMs);
  for (const sample of samples) {
    const distance = Math.abs(sampleTimeMs(sample) - timeMs);
    if (distance < nearestDistance) {
      nearest = sample;
      nearestDistance = distance;
    }
  }
  return nearest;
}

function selectionTimeRange(range: SelectionRange, samples: SessionSample[]): [number, number] | null {
  if (range.startServerReceivedAt && range.endServerReceivedAt) {
    const startTime = new Date(range.startServerReceivedAt).getTime();
    const endTime = new Date(range.endServerReceivedAt).getTime();
    if (Number.isFinite(startTime) && Number.isFinite(endTime)) {
      return [Math.min(startTime, endTime), Math.max(startTime, endTime)];
    }
  }
  return timeRangeForDeviceRange(samples, range);
}

function labelTimeRange(label: EventLabel, samples: SessionSample[]): [number, number] | null {
  if (label.start_server_received_at && label.end_server_received_at) {
    const startTime = new Date(label.start_server_received_at).getTime();
    const endTime = new Date(label.end_server_received_at).getTime();
    if (Number.isFinite(startTime) && Number.isFinite(endTime)) {
      return [Math.min(startTime, endTime), Math.max(startTime, endTime)];
    }
  }
  return timeRangeForDeviceRange(samples, {
    startDeviceMs: label.start_device_ms,
    endDeviceMs: label.end_device_ms,
  });
}

function nearestTimeForDeviceMs(samples: SessionSample[], deviceMs: number): number | null {
  if (samples.length === 0) {
    return null;
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
  return sampleTimeMs(nearest);
}

function timeRangeForDeviceRange(samples: SessionSample[], range: SelectionRange): [number, number] | null {
  const startTime = nearestTimeForDeviceMs(samples, range.startDeviceMs);
  const endTime = nearestTimeForDeviceMs(samples, range.endDeviceMs);
  if (startTime === null || endTime === null) {
    return null;
  }
  return [Math.min(startTime, endTime), Math.max(startTime, endTime)];
}

function Timeline({
  samples,
  labels,
  isSelectionMode,
  onRangeSelected,
  onSelectedRangeChange,
  onRequestOlderWindow,
  onRequestNewerWindow,
  onRequestLatestWindow,
  selectedLabelId,
  selectedRange,
  sampleWindow,
  focusRange,
}: TimelineProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [viewRange, setViewRange] = useState<[number, number] | null>(null);
  const [isFollowingLatest, setIsFollowingLatest] = useState(true);
  const [dragStart, setDragStart] = useState<{ pointerX: number; range: [number, number] } | null>(null);
  const [selectionDrag, setSelectionDrag] = useState<{ timeMs: number; deviceMs: number } | null>(null);
  const [handleDrag, setHandleDrag] = useState<"start" | "end" | null>(null);
  const [selectionDraft, setSelectionDraft] = useState<SelectionRange | null>(null);
  const [selectionTimeDraft, setSelectionTimeDraft] = useState<[number, number] | null>(null);
  const [signalScale, setSignalScale] = useState(1);
  const lastAppliedFocusKeyRef = useRef<string | null>(null);
  const lastWindowRequestKeyRef = useRef<string | null>(null);

  const timelineSamples = useMemo(
    () =>
      [...samples].sort((left, right) => {
        const timeDelta = sampleTimeMs(left) - sampleTimeMs(right);
        if (timeDelta !== 0) {
          return timeDelta;
        }
        return left.sample_index - right.sample_index;
      }),
    [samples],
  );

  const sessionKey = timelineSamples[0]?.session_id ?? null;

  const domain = useMemo<[number, number] | null>(() => {
    if (timelineSamples.length === 0) {
      return null;
    }
    return [sampleTimeMs(timelineSamples[0]), sampleTimeMs(timelineSamples[timelineSamples.length - 1])];
  }, [timelineSamples]);

  useEffect(() => {
    setIsFollowingLatest(true);
    setViewRange(null);
  }, [sessionKey]);

  useEffect(() => {
    setViewRange((current) => {
      if (!domain) {
        return null;
      }
      if (!current || isFollowingLatest) {
        return latestRange(domain);
      }
      return clampRange(current[0], current[1], domain[0], domain[1]);
    });
  }, [domain, isFollowingLatest]);

  useEffect(() => {
    const focusKey = focusRange
      ? `${selectedLabelId ?? "range"}:${focusRange.startDeviceMs}:${focusRange.endDeviceMs}`
      : null;
    if (!focusKey) {
      lastAppliedFocusKeyRef.current = null;
      return;
    }
    if (lastAppliedFocusKeyRef.current === focusKey) {
      return;
    }
    if (domain && focusRange) {
      const timeRange = selectionTimeRange(focusRange, timelineSamples);
      if (timeRange) {
        lastAppliedFocusKeyRef.current = focusKey;
        setIsFollowingLatest(false);
        setViewRange(clampRange(timeRange[0], timeRange[1], domain[0], domain[1]));
      }
    }
  }, [domain, focusRange, selectedLabelId, timelineSamples]);

  const currentRange = viewRange ?? domain;
  const visibleSamples = useMemo(() => {
    if (!currentRange) {
      return [];
    }
    const [start, end] = currentRange;
    return timelineSamples.filter((sample) => {
      const timeMs = sampleTimeMs(sample);
      return timeMs >= start && timeMs <= end;
    });
  }, [currentRange, timelineSamples]);

  useEffect(() => {
    const node = svgRef.current;
    if (!node || !domain || !currentRange) {
      return undefined;
    }

    const svgNode = node;
    const [domainStartMs, domainEndMs] = domain;
    const [viewStartMs, viewEndMs] = currentRange;
    const fullSpan = domainEndMs - domainStartMs;
    const activeSpan = viewEndMs - viewStartMs;
    const plotWidth = WIDTH - LEFT_PAD - RIGHT_PAD;

    function setClampedWheelRange(start: number, end: number) {
      setViewRange(clampRange(start, end, domainStartMs, domainEndMs));
    }

    function pointerToWheelMs(clientX: number): number {
      const rect = svgNode.getBoundingClientRect();
      const svgX = ((clientX - rect.left) / rect.width) * WIDTH;
      const ratio = Math.min(1, Math.max(0, (svgX - LEFT_PAD) / plotWidth));
      return viewStartMs + ratio * activeSpan;
    }

    function handleNativeWheel(event: WheelEvent) {
      event.preventDefault();
      event.stopPropagation();
      setIsFollowingLatest(false);

      if (Math.abs(event.deltaX) > Math.abs(event.deltaY) || event.shiftKey) {
        const deltaMs = event.deltaX * (activeSpan / plotWidth);
        setClampedWheelRange(viewStartMs + deltaMs, viewEndMs + deltaMs);
        return;
      }

      const focus = pointerToWheelMs(event.clientX);
      const nextSpan = Math.min(fullSpan, Math.max(MIN_SPAN_MS, activeSpan * (event.deltaY < 0 ? 0.78 : 1.28)));
      const focusRatio = (focus - viewStartMs) / activeSpan;
      const nextStart = focus - nextSpan * focusRatio;
      setClampedWheelRange(nextStart, nextStart + nextSpan);
    }

    svgNode.addEventListener("wheel", handleNativeWheel, { passive: false });
    return () => svgNode.removeEventListener("wheel", handleNativeWheel);
  }, [currentRange, domain]);

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
  const canLoadOlder = (sampleWindow?.window_start_index ?? 0) > 0;
  const canLoadNewer =
    sampleWindow?.window_end_index !== null &&
    sampleWindow?.window_end_index !== undefined &&
    sampleWindow.window_end_index < sampleWindow.total_sample_count - 1;

  function requestAdjacentWindow(direction: "older" | "newer") {
    const key = `${direction}:${sampleWindow?.window_start_index ?? "none"}:${sampleWindow?.window_end_index ?? "none"}`;
    if (lastWindowRequestKeyRef.current === key) {
      return;
    }
    lastWindowRequestKeyRef.current = key;
    if (direction === "older" && canLoadOlder) {
      onRequestOlderWindow();
    }
    if (direction === "newer" && canLoadNewer) {
      onRequestNewerWindow();
    }
  }

  function setClampedViewRange(start: number, end: number) {
    setIsFollowingLatest(false);
    if (start < domainStart) {
      requestAdjacentWindow("older");
    }
    if (end > domainEnd) {
      requestAdjacentWindow("newer");
    }
    setViewRange(clampRange(start, end, domainStart, domainEnd));
  }

  function setManualViewRange(start: number, end: number) {
    setIsFollowingLatest(false);
    setViewRange(clampRange(start, end, domainStart, domainEnd));
  }

  function xScale(timeMs: number): number {
    return LEFT_PAD + ((timeMs - viewStart) / viewSpan) * plotWidth;
  }

  function pointerToTimeMs(clientX: number): number {
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

  function jumpToLatest() {
    setIsFollowingLatest(true);
    lastWindowRequestKeyRef.current = null;
    if (canLoadNewer) {
      onRequestLatestWindow();
      return;
    }
    setViewRange(latestRange([domainStart, domainEnd], viewSpan));
  }

  function handlePointerDown(event: React.PointerEvent<SVGSVGElement>) {
    event.preventDefault();
    svgRef.current?.setPointerCapture(event.pointerId);
    const pointerTimeMs = Math.round(pointerToTimeMs(event.clientX));
    const pointerSample = nearestSampleByTime(timelineSamples, pointerTimeMs);
    const pointerDeviceMs = pointerSample?.device_ms ?? 0;
    const handleToleranceMs = viewSpan * 0.012;
    const selectedTimeRange = selectedRange ? selectionTimeRange(selectedRange, timelineSamples) : null;

    if (selectedTimeRange && Math.abs(pointerTimeMs - selectedTimeRange[0]) <= handleToleranceMs) {
      setIsFollowingLatest(false);
      setHandleDrag("start");
      return;
    }
    if (selectedTimeRange && Math.abs(pointerTimeMs - selectedTimeRange[1]) <= handleToleranceMs) {
      setIsFollowingLatest(false);
      setHandleDrag("end");
      return;
    }
    if (isSelectionMode) {
      setIsFollowingLatest(false);
      setSelectionDrag({ timeMs: pointerTimeMs, deviceMs: pointerDeviceMs });
      setSelectionDraft({
        startDeviceMs: pointerDeviceMs,
        endDeviceMs: pointerDeviceMs,
        startServerReceivedAt: pointerSample?.server_received_at ?? null,
        endServerReceivedAt: pointerSample?.server_received_at ?? null,
      });
      setSelectionTimeDraft([pointerTimeMs, pointerTimeMs]);
      return;
    }
    setIsFollowingLatest(false);
    setDragStart({ pointerX: event.clientX, range: activeRange });
  }

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const currentTimeMs = Math.round(pointerToTimeMs(event.clientX));
    const currentSample = nearestSampleByTime(timelineSamples, currentTimeMs);
    const currentDeviceMs = currentSample?.device_ms ?? 0;
    if (handleDrag && selectedRange) {
      const currentServerReceivedAt = currentSample?.server_received_at ?? null;
      const nextRange =
        handleDrag === "start"
          ? {
              ...selectedRange,
              startDeviceMs: Math.min(currentDeviceMs, selectedRange.endDeviceMs - 1),
              startServerReceivedAt: currentServerReceivedAt,
            }
          : {
              ...selectedRange,
              endDeviceMs: Math.max(currentDeviceMs, selectedRange.startDeviceMs + 1),
              endServerReceivedAt: currentServerReceivedAt,
            };
      const currentTimeRange = selectionTimeRange(selectedRange, timelineSamples);
      if (currentTimeRange) {
        setSelectionTimeDraft(
          handleDrag === "start"
            ? [Math.min(currentTimeMs, currentTimeRange[1]), currentTimeRange[1]]
            : [currentTimeRange[0], Math.max(currentTimeMs, currentTimeRange[0])],
        );
      }
      onSelectedRangeChange(nextRange);
      return;
    }
    if (selectionDrag !== null) {
      const startDeviceMs = selectionDrag.deviceMs;
      const endDeviceMs = currentDeviceMs;
      const dragStartServerReceivedAt = nearestSampleByTime(timelineSamples, selectionDrag.timeMs)?.server_received_at ?? null;
      const currentServerReceivedAt = currentSample?.server_received_at ?? null;
      setSelectionDraft({
        startDeviceMs: Math.min(startDeviceMs, endDeviceMs),
        endDeviceMs: Math.max(startDeviceMs, endDeviceMs),
        startServerReceivedAt: selectionDrag.timeMs <= currentTimeMs ? dragStartServerReceivedAt : currentServerReceivedAt,
        endServerReceivedAt: selectionDrag.timeMs <= currentTimeMs ? currentServerReceivedAt : dragStartServerReceivedAt,
      });
      setSelectionTimeDraft([Math.min(selectionDrag.timeMs, currentTimeMs), Math.max(selectionDrag.timeMs, currentTimeMs)]);
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
    setSelectionTimeDraft(null);
    setHandleDrag(null);
    setDragStart(null);
  }

  const ticks = Array.from({ length: 6 }, (_, index) => viewStart + (viewSpan * index) / 5);
  const sampleIndexTicks =
    sampleWindow?.window_start_index !== null &&
    sampleWindow?.window_start_index !== undefined &&
    sampleWindow?.window_end_index !== null &&
    sampleWindow?.window_end_index !== undefined
      ? ticks.map((tick) => {
          const ratio = totalSpan > 0 ? (tick - domainStart) / totalSpan : 0;
          return Math.round(sampleWindow.window_start_index! + ratio * (sampleWindow.window_end_index! - sampleWindow.window_start_index!)) + 1;
        })
      : [];
  const visibleSelection = selectionDraft ?? selectedRange;
  const visibleSelectionTimeRange = selectionTimeDraft ?? (visibleSelection ? selectionTimeRange(visibleSelection, timelineSamples) : null);

  return (
    <div className="timeline-card">
      <div className="timeline-toolbar">
        <div>
          <strong>{visibleSamples.length.toLocaleString()}</strong>
          <span> visible points · view {viewPercent.toFixed(1)}%</span>
        </div>
        <div className="zoom-controls" aria-label="Timeline view controls">
          <button disabled={!canLoadOlder} type="button" onClick={() => requestAdjacentWindow("older")}>
            Older
          </button>
          <button type="button" onClick={() => zoomAround((viewStart + viewEnd) / 2, 1.25)}>
            -
          </button>
          <span>{viewPercent.toFixed(1)}%</span>
          <button type="button" onClick={() => zoomAround((viewStart + viewEnd) / 2, 0.8)}>
            +
          </button>
          <button type="button" onClick={() => setManualViewRange(domain[0], domain[1])}>
            Reset
          </button>
          <button type="button" onClick={jumpToLatest}>
            Latest
          </button>
          <button disabled={!canLoadNewer} type="button" onClick={() => requestAdjacentWindow("newer")}>
            Newer
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
              setManualViewRange(nextStart, nextStart + viewSpan);
            }}
            step={0.1}
            type="range"
            value={horizontalPercent}
          />
        </label>
        <label>
          Signal amplitude
          <input
            max={300}
            min={50}
            onChange={(event) => setSignalScale(Number(event.target.value) / 100)}
            step={5}
            type="range"
            value={signalScale * 100}
          />
          <span>{Math.round(signalScale * 100)}% trace height</span>
        </label>
      </div>

      <svg
        aria-label="IMU timeline"
        className="timeline-svg"
        onPointerDown={handlePointerDown}
        onPointerLeave={() => {
          setDragStart(null);
          setSelectionDrag(null);
          setSelectionTimeDraft(null);
          setHandleDrag(null);
        }}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        ref={svgRef}
        role="img"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      >
        <rect className="timeline-background" height={HEIGHT} width={WIDTH} x={0} y={0} />
        {labels.map((label) => {
          const currentLabelTimeRange = labelTimeRange(label, timelineSamples);
          if (!currentLabelTimeRange || currentLabelTimeRange[1] < viewStart || currentLabelTimeRange[0] > viewEnd) {
            return null;
          }
          const x = Math.max(LEFT_PAD, xScale(currentLabelTimeRange[0]));
          const width = Math.max(2, Math.min(WIDTH - RIGHT_PAD, xScale(currentLabelTimeRange[1])) - x);
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

        {visibleSelection && visibleSelectionTimeRange && visibleSelectionTimeRange[1] >= viewStart && visibleSelectionTimeRange[0] <= viewEnd ? (
          <g>
            <rect
              className="selection-overlay"
              height={LANES.length * LANE_HEIGHT}
              rx={10}
              width={Math.max(
                3,
                Math.min(WIDTH - RIGHT_PAD, xScale(visibleSelectionTimeRange[1])) -
                  Math.max(LEFT_PAD, xScale(visibleSelectionTimeRange[0])),
              )}
              x={Math.max(LEFT_PAD, xScale(visibleSelectionTimeRange[0]))}
              y={TOP_PAD}
            />
            {visibleSelectionTimeRange.map((timeMs, index) => (
              <g className="selection-handle" key={index === 0 ? "start" : "end"}>
                <line
                  x1={xScale(timeMs)}
                  x2={xScale(timeMs)}
                  y1={TOP_PAD}
                  y2={TOP_PAD + LANES.length * LANE_HEIGHT}
                />
                <circle cx={xScale(timeMs)} cy={TOP_PAD + 12} r={7} />
              </g>
            ))}
          </g>
        ) : null}

        {LANES.map((lane, laneIndex) => {
          const laneTop = TOP_PAD + laneIndex * LANE_HEIGHT;
          const laneMid = laneTop + LANE_HEIGHT / 2;
          const allValues = visibleSamples.flatMap((sample) => lane.series.map((series) => getValue(sample, series.key)));
          if (allValues.length === 0) {
            return null;
          }
          const minValue = Math.min(...allValues);
          const maxValue = Math.max(...allValues);
          const rawPadding = Math.max(0.1, (maxValue - minValue) * 0.12);
          const rawMid = (maxValue + minValue) / 2;
          const rawHalfSpan = Math.max(0.1, (maxValue - minValue) / 2 + rawPadding) / signalScale;
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

        {ticks.map((tick, index) => (
          <g key={tick}>
            <line className="time-grid" x1={xScale(tick)} x2={xScale(tick)} y1={TOP_PAD} y2={HEIGHT - BOTTOM_PAD} />
            {sampleIndexTicks[index] !== undefined ? (
              <text
                className="sample-tick"
                textAnchor={index === 0 ? "start" : index === ticks.length - 1 ? "end" : "middle"}
                x={xScale(tick)}
                y={18}
              >
                #{sampleIndexTicks[index].toLocaleString()}
              </text>
            ) : null}
            <text
              className="time-tick"
              textAnchor={index === 0 ? "start" : index === ticks.length - 1 ? "end" : "middle"}
              x={xScale(tick)}
              y={HEIGHT - 14}
            >
              {formatTick(new Date(tick), viewSpan)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

export default Timeline;

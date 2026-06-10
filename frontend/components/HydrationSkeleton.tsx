function SkeletonBubble({
  width,
  height = "40px",
  align,
}: {
  width: string;
  height?: string;
  align: "left" | "right";
}) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: align === "right" ? "flex-end" : "flex-start",
      }}
    >
      <div
        className="shimmer"
        style={{
          width,
          height,
          borderRadius:
            align === "right" ? "14px 14px 4px 14px" : "4px 14px 14px 14px",
        }}
      />
    </div>
  );
}

export function HydrationSkeleton() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "14px",
        padding: "20px",
        flex: 1,
      }}
    >
      <SkeletonBubble width="38%" align="right" />
      <SkeletonBubble width="72%" height="56px" align="left" />
      <SkeletonBubble width="58%" align="left" />
      <SkeletonBubble width="44%" align="right" />
      <SkeletonBubble width="78%" height="56px" align="left" />
      <SkeletonBubble width="52%" align="left" />
    </div>
  );
}

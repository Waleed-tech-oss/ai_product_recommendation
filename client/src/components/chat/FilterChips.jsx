export default function FilterChips({ filters = {} }) {
  const chips = [];

  if (filters.category)
    chips.push({
      label: filters.category,
      icon: "📂",
    });

  if (filters.articleType)
    chips.push({
      label: filters.articleType,
      icon: "👟",
    });

  if (filters.color)
    chips.push({
      label: filters.color,
      icon: "🎨",
    });

  if (filters.gender)
    chips.push({
      label: filters.gender,
      icon: "👤",
    });

  if (filters.season)
    chips.push({
      label: filters.season,
      icon: "☀️",
    });

  if (filters.maxPrice)
    chips.push({
      label: `Under Rs.${filters.maxPrice}`,
      icon: "💰",
    });

  if (filters.minPrice)
    chips.push({
      label: `Above Rs.${filters.minPrice}`,
      icon: "💵",
    });

  if (chips.length === 0) return null;

  return (
    <div className="mb-6">

      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
        Active Filters
      </h3>

      <div className="flex flex-wrap gap-2">

        {chips.map((chip, index) => (
          <span
            key={index}
            className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-sm text-cyan-300"
          >
            {chip.icon} {chip.label}
          </span>
        ))}

      </div>

    </div>
  );
}
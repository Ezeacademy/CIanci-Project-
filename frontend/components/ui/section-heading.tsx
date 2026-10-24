type SectionHeadingProps = {
  number: string;
  label: string;
  title: string;
  id: string;
};

export function SectionHeading({
  number,
  label,
  title,
  id,
}: SectionHeadingProps) {
  return (
    <div className="section-heading">
      <p className="eyebrow">
        <span aria-hidden="true">{number} / </span>
        {label}
      </p>
      <h2 id={id}>{title}</h2>
    </div>
  );
}

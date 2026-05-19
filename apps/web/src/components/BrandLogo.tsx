import Image from "next/image";
import Link from "next/link";

type BrandLogoProps = {
  href?: string;
  showWordmark?: boolean;
  className?: string;
};

export default function BrandLogo({
  href = "/",
  showWordmark = true,
  className = "",
}: BrandLogoProps) {
  const content = (
    <>
      <Image
        src="/brand/logo-mark.png"
        alt=""
        width={32}
        height={32}
        priority
        className="size-8 shrink-0"
      />
      {showWordmark ? (
        <Image
          src="/brand/logo-wordmark.png"
          alt="divorse.ai"
          width={168}
          height={40}
          priority
          className="hidden h-7 w-auto sm:block"
        />
      ) : null}
      <span className="sr-only">divorse.ai</span>
    </>
  );

  const classes = `inline-flex items-center gap-2.5 ${className}`.trim();

  if (href) {
    return (
      <Link className={classes} href={href}>
        {content}
      </Link>
    );
  }

  return <div className={classes}>{content}</div>;
}

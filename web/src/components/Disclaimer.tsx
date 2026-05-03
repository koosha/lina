interface DisclaimerProps {
  className?: string;
}

export function Disclaimer({ className }: DisclaimerProps) {
  return (
    <p className={`disclaimer${className ? ` ${className}` : ""}`}>
      Lina can make mistakes. Please review and validate results before relying on them.
    </p>
  );
}

import { Minus, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

interface CandidateSelectorProps {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
}

export const CandidateSelector = ({
  value,
  onChange,
  min = 1,
  max = 50,
}: CandidateSelectorProps) => {
  const increment = () => {
    if (value < max) {
      onChange(value + 1);
    }
  };

  const decrement = () => {
    if (value > min) {
      onChange(value - 1);
    }
  };

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-foreground">
        Top K candidates
      </label>
      <div className="flex items-center gap-3">
        <div className="flex items-center flex-1 bg-card border border-border rounded-lg overflow-hidden">
          <Button
            variant="ghost"
            size="icon"
            onClick={decrement}
            disabled={value <= min}
            className="h-11 rounded-none hover:bg-secondary"
          >
            <Minus className="w-4 h-4" />
          </Button>
          <div className="flex-1 text-center">
            <span className="text-lg font-semibold text-foreground">{value}</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={increment}
            disabled={value >= max}
            className="h-11 rounded-none hover:bg-secondary"
          >
            <Plus className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};

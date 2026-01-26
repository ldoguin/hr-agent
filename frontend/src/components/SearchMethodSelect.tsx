import { Info } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface SearchMethodSelectProps {
  value: string;
  onChange: (value: string) => void;
}

const searchMethods = [
  {
    value: "hybrid",
    label: "Hybrid Search (Recommended)",
    description: "Combines vector and keyword search for best results",
  },
  {
    value: "vector",
    label: "Vector Search",
    description: "Semantic similarity-based matching",
  },
  {
    value: "keyword",
    label: "Keyword Search",
    description: "Traditional keyword-based matching",
  },
];

export const SearchMethodSelect = ({
  value,
  onChange,
}: SearchMethodSelectProps) => {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-foreground">
          Search Method
        </label>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger>
              <Info className="w-4 h-4 text-muted-foreground" />
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              <p className="text-sm">
                Hybrid search combines semantic understanding with keyword
                matching for optimal candidate discovery
              </p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="w-full bg-card border-border h-11">
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="bg-popover border-border">
          {searchMethods.map((method) => (
            <SelectItem
              key={method.value}
              value={method.value}
              className="cursor-pointer"
            >
              {method.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
};

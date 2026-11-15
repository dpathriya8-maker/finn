import { BriefHeader } from "@/components/brief/BriefHeader";
import { MorningBrief } from "@/components/brief/MorningBrief";

export default function Home() {
  return (
    <>
      <BriefHeader />
      <div className="mt-5">
        <MorningBrief />
      </div>
    </>
  );
}

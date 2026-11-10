import { useState } from "react";
import HeroBackground from "../components/landing/HeroBackground";
import LandingNav from "../components/landing/LandingNav";
import Hero from "../components/landing/Hero";
import UploadModal from "../components/modals/UploadModal";
import RepositoryModal from "../components/modals/RepositoryModal";

type ModalName = "upload" | "repo" | null;

export default function LandingPage() {
  const [openModal, setOpenModal] = useState<ModalName>(null);

  function closeModal() {
    setOpenModal(null);
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-base text-main">
      <HeroBackground />
      <LandingNav />
      <Hero
        onUploadClick={() => setOpenModal("upload")}
        onConnectClick={() => setOpenModal("repo")}
      />

      {openModal === "upload" && <UploadModal onClose={closeModal} />}
      {openModal === "repo" && <RepositoryModal onClose={closeModal} />}
    </div>
  );
}
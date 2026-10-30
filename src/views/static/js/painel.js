function toggleCard(id) {
    const details = document.getElementById(`details-${id}`);
    const seta = document.getElementById(`seta-${id}`);

    details.classList.toggle("open");

    seta.style.transform = details.classList.contains("open")
        ? "rotate(180deg)"
        : "rotate(0deg)";
}

function salvarDenuncia(btn) {
    const denunciaId = btn.getAttribute("data-id");

    const form = btn.closest(".form-analise");

    const status = form.querySelector("[name='status']").value;
    const severidade = form.querySelector("[name='severidade']").value;
    const responsavel = form.querySelector("[name='responsavel']").value;

    if (status === "finalizado") {
        const confirmar = confirm("Confirma a finalização desta denúncia?");

        if (!confirmar) {
            return;
        }
    }

    const depoimentoVitima = form.querySelector("[name='depoimento_vitima']").value;
    const depoimentoAcusado = form.querySelector("[name='depoimento_acusado']").value;
    const depoimentoTestemunha = form.querySelector("[name='depoimento_testemunha']").value;
    const depoimentoAdmin = form.querySelector("[name='depoimento_admin']").value;

    const dados = {
        status: status,
        severidade: severidade,
        responsavel: responsavel,
        depoimento_vitima: depoimentoVitima,
        depoimento_acusado: depoimentoAcusado,
        depoimento_testemunha: depoimentoTestemunha,
        depoimento_admin: depoimentoAdmin
    };

    fetch(`/admin/denuncia/${denunciaId}/atualizar`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').content
        },
        body: JSON.stringify(dados)
    })
    .then(response => response.json())
    .then(data => {
        console.log(data);

        if (data.sucesso) {
            mostrarToast("Denúncia atualizada com sucesso!", "success");
            setTimeout(() => window.location.reload(), 900);
        } else {
            mostrarToast(data.mensagem || "Erro ao atualizar denúncia.", "error");
        }
    })
    .catch(error => {
        console.error("Erro:", error);
        mostrarToast("Erro ao atualizar denúncia. Veja o console.", "error");
    });
}

function mostrarToast(mensagem, tipo = "success") {
    let container = document.querySelector(".toast-container");

    if (!container) {
        container = document.createElement("div");
        container.className = "toast-container";
        document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast ${tipo}`;
    toast.textContent = mensagem;
    container.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3500);
}

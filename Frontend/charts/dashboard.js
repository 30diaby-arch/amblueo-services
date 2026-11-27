import { init, use } from "echarts/core";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

use([BarChart, LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

const données = JSON.parse(document.getElementById("dashboard-data").textContent);
const devise = new Intl.NumberFormat("fr", { style: "currency", currency: données.currency });
const axes = new Intl.NumberFormat("fr", { notation: "compact", maximumFractionDigits: 1 });
const couleurs = ["#1805a4", "#e4770b", "#158075", "#7259a8", "#5368aa", "#9b4567", "#64748b"];
const séries = ["Encaissements", "Décaissements"];
const réduireAnimations = matchMedia("(prefers-reduced-motion: reduce)").matches;

function monter(id, options) {
    const cible = document.getElementById(id);
    if (!cible) return;
    cible.hidden = false;
    try {
        const graphique = init(cible);
        graphique.setOption({ color: couleurs, animation: !réduireAnimations, ...options });
        new ResizeObserver(() => graphique.resize()).observe(cible);
        const secours = document.getElementById(id + "-fallback");
        if (secours) secours.hidden = true;
    } catch (erreur) {
        cible.hidden = true;
        console.error("Le graphique du tableau de bord n’a pas pu être affiché.", erreur);
    }
}

function axesFinanciers(labels) {
    return {
        grid: { left: 8, right: 12, top: 44, bottom: 12, containLabel: true },
        legend: { top: 0, data: séries },
        tooltip: { trigger: "axis", renderMode: "richText", valueFormatter: (valeur) => devise.format(valeur) },
        xAxis: { type: "category", data: labels, axisLabel: { hideOverlap: true } },
        yAxis: { type: "value", axisLabel: { formatter: (valeur) => axes.format(valeur) } },
    };
}

monter("dashboard-flux-chart", {
    ...axesFinanciers(données.flow.map((point) => point.label)),
    series: [
        { name: séries[0], type: "line", data: données.flow.map((point) => Number(point.income)), areaStyle: { opacity: 0.10 } },
        { name: séries[1], type: "line", data: données.flow.map((point) => Number(point.expense)), lineStyle: { type: "dashed" } },
    ],
});

monter("dashboard-budget-chart", {
    tooltip: { trigger: "item", renderMode: "richText", valueFormatter: (valeur) => devise.format(valeur) },
    series: [{
        type: "pie", radius: ["51%", "78%"], label: { show: false },
        data: données.budgets.map((budget) => ({ name: budget.label, value: Number(budget.amount) })),
    }],
});

monter("dashboard-echeances-chart", {
    ...axesFinanciers(données.deadlines.map((lit) => lit.label)),
    legend: { top: 0, data: ["À encaisser", "À payer"] },
    series: [
        { name: "À encaisser", type: "bar", data: données.deadlines.map((lit) => Number(lit.income)) },
        { name: "À payer", type: "bar", data: données.deadlines.map((lit) => Number(lit.expense)) },
    ],
});
